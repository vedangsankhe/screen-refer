"""One place that turns (age, sex, raw answers) into a validated, scored result.
Used when a screening is submitted and again when a DOB/sex correction triggers re-evaluation."""
from .form import get_config, resolve_visible, validate_answers
from .scoring import score_answers


def run(age: int, sex: str, answers: dict) -> dict:
    config = get_config()
    visible = resolve_visible(config, age, sex, answers)
    errors = validate_answers(config, visible, answers)
    used = {k: v for k, v in answers.items() if k in visible}
    dropped = {k: v for k, v in answers.items() if k not in visible}
    score, level, reasons = score_answers(used, age, sex)
    return {"visible": visible, "errors": errors, "answers": used, "discarded": dropped,
            "score": score, "level": level, "reasons": reasons}
