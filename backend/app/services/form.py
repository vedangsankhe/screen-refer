"""Loads form_config.json and works out which questions are visible / valid."""
import json
from functools import lru_cache
from pathlib import Path

from .visibility import evaluate

CONFIG_PATH = Path(__file__).resolve().parent.parent / "form_config.json"


@lru_cache
def get_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def question_map(config: dict) -> dict:
    return {q["id"]: q for q in config["questions"]}


def resolve_visible(config: dict, age: int, sex: str, answers: dict) -> list[str]:
    """Walk the questions in order. A question counts as visible only if its rule passes using
    age, sex and the answers to *visible* earlier questions. So hiding a parent hides its whole
    chain of follow-ups (cascade)."""
    ctx = {"age": age, "sex": sex}
    visible = []
    for q in config["questions"]:
        if evaluate(q.get("visibleIf"), ctx):
            visible.append(q["id"])
            if q["id"] in answers:
                ctx[q["id"]] = answers[q["id"]]
    return visible


def validate_answers(config: dict, visible: list[str], answers: dict) -> list[str]:
    qs = question_map(config)
    errors = [f"Unknown question '{k}'" for k in answers if k not in qs]
    for qid in visible:
        q, v = qs[qid], answers.get(qid)
        if v is None or v == "":
            errors.append(f"Answer required: {q['label']['en']}")
        elif q["type"] == "yesno" and v not in ("yes", "no"):
            errors.append(f"'{qid}' must be yes or no")
        elif q["type"] == "choice" and v not in [o["value"] for o in q["options"]]:
            errors.append(f"'{qid}' has an invalid option")
        elif q["type"] == "number":
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                errors.append(f"'{qid}' must be a number")
            elif not (q.get("min", float("-inf")) <= v <= q.get("max", float("inf"))):
                errors.append(f"'{qid}' must be between {q.get('min')} and {q.get('max')}")
    return errors


def describe_answers(config: dict, answers: dict) -> list[dict]:
    """Human-readable answers (for the result screen and the AI prompt)."""
    out = []
    for q in config["questions"]:
        if q["id"] not in answers:
            continue
        v = answers[q["id"]]
        label_en, label_hi = str(v), str(v)
        if q["type"] == "yesno":
            label_en, label_hi = ("Yes", "हाँ") if v == "yes" else ("No", "नहीं")
        elif q["type"] == "choice":
            opt = next((o for o in q["options"] if o["value"] == v), None)
            if opt:
                label_en, label_hi = opt["label"]["en"], opt["label"]["hi"]
        elif q.get("unit"):
            label_en = f"{v} {q['unit']['en']}"
            label_hi = f"{v} {q['unit']['hi']}"
        out.append({"id": q["id"], "question": q["label"]["en"], "question_hi": q["label"]["hi"],
                    "answer": v, "answer_label": label_en, "answer_label_hi": label_hi})
    return out
