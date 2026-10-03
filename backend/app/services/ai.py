"""AI summary for the doctor. The LLM is optional: any failure returns None and the app carries on.
The prompt contains answers and the risk result only, never the patient's name or phone."""
import json
import re

import httpx
from pydantic import BaseModel, ValidationError, field_validator

from .. import config

DEFAULT_MODELS = {"gemini": "gemini-2.5-flash", "anthropic": "claude-haiku-4-5-20251001"}
UNAVAILABLE = "AI summary unavailable. The screening result is unaffected."

PROMPT = """You help a doctor review a community health screening done by a field health worker.
Write a short plain-language summary (3 to 4 sentences) of the screening below: who was screened,
what stood out, and why the risk level came out as it did. Do NOT diagnose and do NOT recommend treatment.
Write it twice: once in simple English ("en") and once in simple Hindi in Devanagari script ("hi").
Reply with ONLY a JSON object, no markdown, exactly like: {{"en": "...", "hi": "..."}}

Patient: {age} years old, {sex}
Risk level (calculated by rules): {level} (score {score})
Rules that fired: {reasons}
Answers:
{answers}
"""


class SummaryOut(BaseModel):
    en: str
    hi: str

    @field_validator("en", "hi")
    @classmethod
    def sane_text(cls, v: str) -> str:
        v = v.strip()
        if not 20 <= len(v) <= 2000:
            raise ValueError("summary length looks wrong")
        return v

    @field_validator("hi")
    @classmethod
    def must_be_devanagari(cls, v: str) -> str:
        if not re.search(r"[\u0900-\u097F]", v):
            raise ValueError("Hindi text is not in Devanagari")
        return v


def model_name() -> str:
    return config.LLM_MODEL or DEFAULT_MODELS.get(config.LLM_PROVIDER, "")


def _call_llm(prompt: str) -> str:
    """Returns the raw text of the model's reply. Raises on any network/HTTP problem."""
    if not config.LLM_API_KEY:
        raise RuntimeError("No LLM key configured")
    model = model_name()
    if config.LLM_PROVIDER == "anthropic":
        r = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": config.LLM_API_KEY, "anthropic-version": "2023-06-01"},
            json={"model": model, "max_tokens": 900, "messages": [{"role": "user", "content": prompt}]},
            timeout=config.LLM_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()["content"][0]["text"]
    if config.LLM_PROVIDER == "gemini":
        r = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            headers={"x-goog-api-key": config.LLM_API_KEY},
            json={"contents": [{"parts": [{"text": prompt}]}],
                  "generationConfig": {"responseMimeType": "application/json"}},
            timeout=config.LLM_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    raise RuntimeError(f"Unknown LLM_PROVIDER '{config.LLM_PROVIDER}'")


def _extract_json(text: str) -> dict:
    text = re.sub(r"```(?:json)?", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in reply")
    return json.loads(text[start:end + 1])


def generate_summary(age: int, sex: str, level: str, score: int, reasons: list[str], answers: list[dict]) -> SummaryOut | None:
    prompt = PROMPT.format(
        age=age, sex=sex, level=level, score=score,
        reasons="; ".join(reasons) or "none",
        answers="\n".join(f"- {a['question']} -> {a['answer_label']}" for a in answers),
    )
    try:
        return SummaryOut(**_extract_json(_call_llm(prompt)))
    except (httpx.HTTPError, ValidationError, ValueError, KeyError, IndexError, TypeError, RuntimeError):
        # timeout, 4xx/5xx, junk, missing fields, wrong script, no key: all end up here
        return None
