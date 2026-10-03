"""Risk scoring. Runs on the server only; the frontend never calculates a risk level.

Each rule is {"id", "text", "when": <condition>, "points": n}  or  {..., "red_flag": True}.
A red flag makes the result High no matter what the points say.
Conditions use the same rule language as the form (see visibility.py).
"""
from .visibility import evaluate

LEVELS = ["Low", "Medium", "High"]
MEDIUM_FROM = 3
HIGH_FROM = 6

RULES = [
    # --- red flags: always High ---
    {"id": "rf_chest_breathless", "text": "Chest pain together with breathlessness",
     "when": {"q": "chest_pain_breathless", "eq": "yes"}, "red_flag": True},
    {"id": "rf_blood_sputum", "text": "Coughing blood",
     "when": {"q": "blood_in_sputum", "eq": "yes"}, "red_flag": True},
    {"id": "rf_pregnancy_danger", "text": "Pregnancy danger signs",
     "when": {"q": "pregnancy_danger_signs", "eq": "yes"}, "red_flag": True},
    {"id": "rf_muac_red", "text": "Child's arm band is in the red zone (severe malnutrition)",
     "when": {"q": "child_muac_red", "eq": "yes"}, "red_flag": True},
    {"id": "rf_infant_fever", "text": "Fever in a child under 1 year",
     "when": {"all": [{"q": "age", "lt": 1}, {"q": "fever", "eq": "yes"}]}, "red_flag": True},
    # --- points ---
    {"id": "fever", "text": "Fever in the last 2 weeks", "when": {"q": "fever", "eq": "yes"}, "points": 1},
    {"id": "fever_5d", "text": "Fever for 5 days or more", "when": {"q": "fever_days", "gte": 5}, "points": 2},
    {"id": "cough_2_3w", "text": "Cough for 2 to 3 weeks", "when": {"q": "cough_duration", "eq": "2to3"}, "points": 1},
    {"id": "cough_3w", "text": "Cough for more than 3 weeks", "when": {"q": "cough_duration", "eq": "gt3"}, "points": 2},
    {"id": "chest_pain", "text": "Chest pain", "when": {"q": "chest_pain", "eq": "yes"}, "points": 2},
    {"id": "weight_loss", "text": "Unexplained weight loss", "when": {"q": "weight_loss", "eq": "yes"}, "points": 2},
    {"id": "diabetes", "text": "Known diabetes", "when": {"q": "diabetes", "eq": "yes"}, "points": 1},
    {"id": "high_bp", "text": "Known high blood pressure", "when": {"q": "high_bp", "eq": "yes"}, "points": 1},
    {"id": "smoker", "text": "Current smoker or tobacco user", "when": {"q": "smoker", "eq": "current"}, "points": 1},
    {"id": "heavy_smoker", "text": "10 or more cigarettes/bidis a day", "when": {"q": "cigs_per_day", "gte": 10}, "points": 1},
    {"id": "irregular_periods", "text": "Irregular periods", "when": {"q": "menstrual_irregular", "eq": "yes"}, "points": 1},
    {"id": "pregnant", "text": "Currently pregnant", "when": {"q": "pregnant", "eq": "yes"}, "points": 1},
    {"id": "child_feeding", "text": "Child is feeding poorly", "when": {"q": "child_poor_feeding", "eq": "yes"}, "points": 2},
    {"id": "age_60", "text": "Age 60 or above", "when": {"q": "age", "gte": 60}, "points": 1},
]


def score_answers(answers: dict, age: int, sex: str) -> tuple[int, str, list[dict]]:
    """`answers` must already contain only answers to visible questions."""
    ctx = {**answers, "age": age, "sex": sex}
    score, red_flag, reasons = 0, False, []
    for rule in RULES:
        if not evaluate(rule["when"], ctx):
            continue
        if rule.get("red_flag"):
            red_flag = True
            reasons.append({"id": rule["id"], "text": rule["text"], "points": 0, "red_flag": True})
        else:
            score += rule["points"]
            reasons.append({"id": rule["id"], "text": rule["text"], "points": rule["points"], "red_flag": False})
    level = "High" if (red_flag or score >= HIGH_FROM) else "Medium" if score >= MEDIUM_FROM else "Low"
    return score, level, reasons
