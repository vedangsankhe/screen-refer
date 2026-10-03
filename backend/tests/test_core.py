import json
import uuid
from pathlib import Path

import pytest

from app.services.form import get_config, resolve_visible
from app.services.normalize import name_key, name_similarity, normalize_phone
from app.services.scoring import score_answers
from app.services.visibility import evaluate
from .conftest import dob_for_age, login, make_patient

CASES = json.loads((Path(__file__).parent / "visibility_cases.json").read_text())


# ---------- pure functions ----------
@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_visibility_cases(case):
    assert evaluate(case["cond"], case["ctx"]) is case["expect"]


@pytest.mark.parametrize("raw", ["+919876543210", "+91 98765 43210", "09876543210", "9876543210",
                                 "98765-43210", "0091 9876543210", "९८७६५४३२१०"])
def test_phone_formats(raw):
    assert normalize_phone(raw) == "9876543210"


@pytest.mark.parametrize("raw", ["12345", "5876543210", "+91 98765", "abc", ""])
def test_phone_rejects_bad(raw):
    with pytest.raises(ValueError):
        normalize_phone(raw)


def test_name_matching_across_spellings_and_scripts():
    assert name_key("Rahul") == name_key("Rahool") == name_key("राहुल")
    assert name_similarity("Rahul Kumar", "राहुल कुमार") >= 80
    assert name_similarity("Rahul Sharma", "Rahool Sharma") >= 80
    assert name_similarity("Rahul Sharma", "Sunita Devi") < 60


def test_form_config_is_consistent():
    cfg = get_config()
    ids = [q["id"] for q in cfg["questions"]]
    assert len(ids) == len(set(ids)) and 14 <= len(ids) <= 20
    seen = set()
    for q in cfg["questions"]:
        assert q["label"]["en"] and q["label"]["hi"]
        seen.add(q["id"])


def test_six_year_old_boy_gets_no_menstrual_or_adult_questions():
    visible = resolve_visible(get_config(), 6, "male", {})
    assert "menstrual_irregular" not in visible and "pregnant" not in visible
    assert "diabetes" not in visible and "chest_pain" not in visible
    assert "child_poor_feeding" not in visible          # that one is for under-5s only
    assert "child_poor_feeding" in resolve_visible(get_config(), 3, "male", {})


def test_follow_up_cascade():
    cfg = get_config()
    a = {"cough": "yes", "cough_duration": "gt3", "blood_in_sputum": "yes"}
    assert "blood_in_sputum" in resolve_visible(cfg, 30, "male", a)
    a["cough"] = "no"  # hide the parent -> the whole chain disappears
    v = resolve_visible(cfg, 30, "male", a)
    assert "cough_duration" not in v and "blood_in_sputum" not in v


def test_scoring_levels_and_red_flags():
    assert score_answers({"fever": "no"}, 30, "male")[1] == "Low"
    assert score_answers({"fever": "yes", "fever_days": 6}, 30, "male")[:2] == (3, "Medium")
    assert score_answers({"chest_pain": "yes", "chest_pain_breathless": "yes"}, 30, "male")[1] == "High"  # red flag despite 2 points
    assert score_answers({"fever": "yes"}, 0, "male")[1] == "High"  # infant fever


# ---------- helpers for API tests ----------
def base_answers(**over):
    a = {"fever": "no", "cough": "no", "chest_pain": "no", "weight_loss": "no", "diabetes": "no",
         "high_bp": "no", "smoker": "never"}
    a.update(over)
    return a


def screen(client, headers, patient_id, answers, cid=None):
    return client.post("/screenings", json={"patient_id": patient_id, "client_uuid": cid or str(uuid.uuid4()),
                                            "answers": answers}, headers=headers)


# ---------- roles & isolation ----------
def test_requires_login(client):
    assert client.get("/patients").status_code == 401
    assert client.get("/form-config").status_code == 401


def test_worker_gets_403_on_doctor_endpoints(client, worker1, doctor):
    pid = make_patient(client, worker1).json()["id"]
    sid = screen(client, worker1, pid, base_answers()).json()["id"]
    assert client.post(f"/screenings/{sid}/review", json={"decision": "accept"}, headers=worker1).status_code == 403
    assert client.post(f"/screenings/{sid}/summary", headers=worker1).status_code == 403
    assert client.get(f"/audit?entity=screening&entity_id={sid}", headers=worker1).status_code == 403
    assert client.post(f"/screenings/{sid}/review", json={"decision": "accept"}, headers=doctor).status_code == 200


def test_worker_sees_only_own_records_doctor_sees_all(client, worker1, worker2, doctor):
    p1 = make_patient(client, worker1, name="Asha Patient", phone="9000000001").json()["id"]
    p2 = make_patient(client, worker2, name="Meena Patient", phone="9000000002").json()["id"]
    s1 = screen(client, worker1, p1, base_answers()).json()["id"]
    assert [p["id"] for p in client.get("/patients", headers=worker1).json()["items"]] == [p1]
    assert client.get(f"/patients/{p2}", headers=worker1).status_code == 404
    assert client.patch(f"/patients/{p2}", json={"name": "Hacked"}, headers=worker1).status_code == 404
    assert client.delete(f"/patients/{p2}", headers=worker1).status_code == 404
    assert client.get(f"/screenings/{s1}", headers=worker2).status_code == 404
    assert screen(client, worker2, p1, base_answers()).status_code == 404  # can't screen someone else's patient
    assert client.get("/screenings", headers=worker2).json()["total"] == 0
    assert client.get("/patients", headers=doctor).json()["total"] == 2
    assert client.get(f"/screenings/{s1}", headers=doctor).status_code == 200


# ---------- patients ----------
def test_soft_delete_search_and_pagination(client, worker1):
    names = ["Anil Gupta", "Bhavna Joshi", "Chetan Kale", "Divya Nair", "Eshwar Pillai"]
    for i, n in enumerate(names):
        make_patient(client, worker1, name=n, phone=f"90000000{i:02d}", dob="1990-01-01")
    page = client.get("/patients?page=2&page_size=2", headers=worker1).json()
    assert page["total"] == 5 and page["pages"] == 3 and len(page["items"]) == 2
    pid = client.get("/patients?q=Divya", headers=worker1).json()["items"][0]["id"]
    assert client.delete(f"/patients/{pid}", headers=worker1).status_code == 200
    assert client.get(f"/patients/{pid}", headers=worker1).status_code == 404
    assert client.get("/patients", headers=worker1).json()["total"] == 4
    assert client.get("/patients?q=Divya", headers=worker1).json()["total"] == 0


def test_search_devanagari_phone_and_transliteration(client, worker1):
    make_patient(client, worker1, name="राहुल शर्मा", phone="+91 98765 43210")
    make_patient(client, worker1, name="Sunita Devi", phone="09123456789", dob="1985-03-03", sex="female")
    for q in ["राहुल", "शर्मा", "rahul", "98765", "+919876543210", "09876543210"]:
        r = client.get("/patients", params={"q": q}, headers=worker1).json()
        assert r["total"] == 1 and r["items"][0]["name"] == "राहुल शर्मा", q
    assert client.get("/patients?q=sunita", headers=worker1).json()["items"][0]["phone"] == "9123456789"


def test_invalid_input_rejected(client, worker1):
    assert make_patient(client, worker1, phone="12345").status_code == 422
    assert make_patient(client, worker1, name="   ").status_code == 422
    assert make_patient(client, worker1, dob="2999-01-01").status_code == 422


def test_duplicate_registration(client, worker1, worker2):
    assert make_patient(client, worker1, name="Rahul Sharma", phone="+91 98765 43210").status_code == 201
    # same phone typed another way, name spelled differently / in Devanagari
    for name, phone in [("Rahool Sharma", "09876543210"), ("राहुल शर्मा", "9876543210")]:
        r = make_patient(client, worker1, name=name, phone=phone)
        assert r.status_code == 409 and r.json()["detail"]["code"] == "possible_duplicate"
        assert len(r.json()["detail"]["candidates"]) == 1
    # a family member sharing the phone is allowed
    assert make_patient(client, worker1, name="Sunita Devi", dob="1960-01-01", phone="9876543210").status_code == 201
    # "create anyway"
    assert make_patient(client, worker1, name="Rahool Sharma", phone="9876543210", force_create=True).status_code == 201
    # another worker is warned but sees no details of the other worker's patient
    r = make_patient(client, worker2, name="Rahul Sharma", phone="9876543210")
    assert r.status_code == 409 and r.json()["detail"]["candidates"] == [] and r.json()["detail"]["hidden_matches"] >= 1


# ---------- screening ----------
def test_screening_prunes_hidden_answers_and_scores_only_visible(client, worker1):
    pid = make_patient(client, worker1, dob=dob_for_age(30)).json()["id"]
    # fever=no but fever_days=9 was left over from an earlier "yes"
    r = screen(client, worker1, pid, base_answers(fever_days=9))
    assert r.status_code == 201
    body = r.json()
    assert body["risk_level"] == "Low" and body["score"] == 0
    assert "fever_days" not in [a["id"] for a in body["answers"]]
    assert [a["id"] for a in body["discarded_answers"]] == ["fever_days"]
    assert body["disclaimer"] == "Screening aid only, not a diagnosis."


def test_six_year_old_cannot_answer_menstrual(client, worker1):
    pid = make_patient(client, worker1, sex="female", dob=dob_for_age(6)).json()["id"]
    a = {"fever": "no", "cough": "no", "weight_loss": "no"}
    r = screen(client, worker1, pid, {**a, "menstrual_irregular": "yes"})
    assert r.status_code == 201 and "menstrual_irregular" in [d["id"] for d in r.json()["discarded_answers"]]


def test_validation_errors(client, worker1):
    pid = make_patient(client, worker1, dob=dob_for_age(30)).json()["id"]
    assert screen(client, worker1, pid, {"fever": "no"}).status_code == 422                 # missing answers
    assert screen(client, worker1, pid, base_answers(fever="maybe")).status_code == 422       # bad value
    assert screen(client, worker1, pid, base_answers(nonsense="x")).status_code == 422        # unknown question
    assert screen(client, worker1, pid, base_answers(fever="yes", fever_days=99)).status_code == 422


def test_red_flag_gives_high(client, worker1):
    pid = make_patient(client, worker1, dob=dob_for_age(45)).json()["id"]
    r = screen(client, worker1, pid, base_answers(chest_pain="yes", chest_pain_breathless="yes"))
    assert r.json()["risk_level"] == "High"
    assert any(x["red_flag"] for x in r.json()["risk_reasons"])


def test_resubmitting_same_client_uuid_is_idempotent(client, worker1):
    pid = make_patient(client, worker1, dob=dob_for_age(30)).json()["id"]
    cid = str(uuid.uuid4())
    first = screen(client, worker1, pid, base_answers(), cid)
    second = screen(client, worker1, pid, base_answers(), cid)
    assert first.status_code == 201 and second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert client.get("/screenings", headers=worker1).json()["total"] == 1


def test_dob_correction_after_screening(client, worker1, doctor):
    pid = make_patient(client, worker1, sex="female", dob=dob_for_age(3)).json()["id"]
    a = {"fever": "no", "cough": "no", "child_poor_feeding": "no", "child_muac_red": "no"}
    s = screen(client, worker1, pid, a).json()
    assert s["age_at_screening"] == 3
    # DOB was typed wrong: she is actually 30
    assert client.patch(f"/patients/{pid}", json={"dob": dob_for_age(30)}, headers=worker1).status_code == 200
    after = client.get(f"/screenings/{s['id']}", headers=doctor).json()
    assert after["risk_level"] == s["risk_level"] and after["age_at_screening"] == 3   # history untouched
    re = after["reevaluation"]
    assert re["old_age"] == 3 and re["new_age"] == 30 and re["needs_rescreen"] is True
    assert "chest_pain" in re["unanswered_questions"] and "child_poor_feeding" in re["ignored_answers"]
    actions = [(e["entity"], e["action"]) for e in after["audit"]]
    assert ("patient", "update") in actions and ("screening", "flagged_for_reevaluation") in actions
    # fixing it back clears the warning
    client.patch(f"/patients/{pid}", json={"dob": dob_for_age(3)}, headers=worker1)
    assert client.get(f"/screenings/{s['id']}", headers=doctor).json()["reevaluation"] is None


# ---------- doctor review ----------
def test_override_needs_reason_and_is_audited(client, worker1, doctor):
    pid = make_patient(client, worker1, dob=dob_for_age(30)).json()["id"]
    sid = screen(client, worker1, pid, base_answers()).json()["id"]
    url = f"/screenings/{sid}/review"
    assert client.post(url, json={"decision": "override", "final_level": "High"}, headers=doctor).status_code == 422
    assert client.post(url, json={"decision": "override", "final_level": "High", "reason": "  "}, headers=doctor).status_code == 422
    assert client.post(url, json={"decision": "override", "final_level": "Low", "reason": "same level"}, headers=doctor).status_code == 422
    r = client.post(url, json={"decision": "override", "final_level": "High", "reason": "Looks unwell on visit"}, headers=doctor)
    assert r.status_code == 200 and r.json()["final_level"] == "High" and r.json()["risk_level"] == "Low"
    entry = [e for e in r.json()["audit"] if e["action"] == "review_override"][0]
    assert entry["actor"] == "Dr. Rao" and entry["old_value"]["final_level"] == "Low"
    assert entry["new_value"]["final_level"] == "High" and entry["new_value"]["reason"] == "Looks unwell on visit"
    assert entry["created_at"]
    # worker sees the final level but no audit trail
    w = client.get(f"/screenings/{sid}", headers=worker1).json()
    assert w["final_level"] == "High" and "audit" not in w


# ---------- AI summary ----------
def test_ai_failures_never_break_the_app(client, worker1, doctor, monkeypatch):
    from app.services import ai
    pid = make_patient(client, worker1, dob=dob_for_age(30)).json()["id"]
    sid = screen(client, worker1, pid, base_answers()).json()["id"]
    url = f"/screenings/{sid}/summary"

    r = client.post(url, headers=doctor)  # no key configured
    assert r.status_code == 200 and r.json()["status"] == "unavailable"

    import httpx
    def timeout(prompt): raise httpx.ReadTimeout("slow")
    monkeypatch.setattr(ai, "_call_llm", timeout)
    assert client.post(url, headers=doctor).json()["status"] == "unavailable"

    for junk in ["Sorry, I can't help with that", "{not json", '{"en": "short"}', '{"en": "x", "hi": "y"}',
                 '{"en": "This is a long enough english summary text.", "hi": "this is not devanagari but is long enough"}']:
        monkeypatch.setattr(ai, "_call_llm", lambda p, j=junk: j)
        assert client.post(url, headers=doctor).json()["status"] == "unavailable", junk

    good = '```json\n{"en": "A 30 year old man with no concerning answers.", "hi": "30 वर्षीय पुरुष, कोई चिंताजनक उत्तर नहीं।"}\n```'
    prompts = []
    monkeypatch.setattr(ai, "_call_llm", lambda p: prompts.append(p) or good)
    r = client.post(url, headers=doctor).json()
    assert r["status"] == "ok" and r["en"] and r["hi"]
    assert "Rahul" not in prompts[0] and "9876543210" not in prompts[0]   # no name or phone sent to the LLM
    monkeypatch.setattr(ai, "_call_llm", timeout)  # cached now, so a later failure doesn't matter
    assert client.post(url, headers=doctor).json()["cached"] is True
    assert client.get(f"/screenings/{sid}", headers=doctor).json()["ai_summary"]["status"] == "ok"
