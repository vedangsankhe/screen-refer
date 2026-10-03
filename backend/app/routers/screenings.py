from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..access import (audit, get_patient_or_404, get_screening_or_404, iso, today_ist, visible_screenings)
from ..database import get_db
from ..models import AISummary, AuditLog, Patient, Review, Screening, User
from ..security import current_user, require_doctor
from ..services import ai
from ..services.engine import run
from ..services.form import describe_answers, get_config
from ..services.visibility import age_on

router = APIRouter(tags=["screenings"])
DISCLAIMER = "Screening aid only, not a diagnosis."
Level = Literal["Low", "Medium", "High"]


class ScreeningIn(BaseModel):
    patient_id: int
    client_uuid: str = Field(min_length=8, max_length=64)  # generated once per form on the phone
    answers: dict


class ReviewIn(BaseModel):
    decision: Literal["accept", "override"]
    final_level: Level | None = None
    reason: str | None = Field(default=None, max_length=1000)

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, v):
        return v.strip() if v else v


def list_item(s: Screening, patient: Patient) -> dict:
    return {
        "id": s.id, "patient_id": s.patient_id, "patient_name": patient.name, "created_at": iso(s.created_at),
        "age_at_screening": s.age_at_screening, "score": s.score, "risk_level": s.risk_level,
        "final_level": s.final_level, "review_decision": s.review_decision,
        "needs_reevaluation": bool(s.reevaluation),
    }


def detail(db: Session, s: Screening, user: User) -> dict:
    patient = db.get(Patient, s.patient_id)
    out = {
        **list_item(s, patient),
        "disclaimer": DISCLAIMER,
        "patient": {"id": patient.id, "name": patient.name, "sex": patient.sex, "dob": patient.dob.isoformat(),
                    "phone": patient.phone},
        "form_version": s.form_version, "dob_at_screening": s.dob_at_screening.isoformat(),
        "sex_at_screening": s.sex_at_screening,
        "risk_reasons": s.risk_reasons, "answers": describe_answers(get_config(), s.answers),
        "discarded_answers": describe_answers(get_config(), s.discarded_answers),
        "reevaluation": s.reevaluation,
        "reviews": [{"decision": r.decision, "previous_level": r.previous_level, "final_level": r.final_level,
                     "reason": r.reason, "created_at": iso(r.created_at), "doctor": db.get(User, r.doctor_id).name}
                    for r in db.query(Review).filter(Review.screening_id == s.id).order_by(Review.id)],
    }
    if user.role == "doctor":
        out["ai_summary"] = _summary_out(db.query(AISummary).filter(AISummary.screening_id == s.id).first())
        entries = db.query(AuditLog).filter(
            ((AuditLog.entity == "screening") & (AuditLog.entity_id == s.id)) |
            ((AuditLog.entity == "patient") & (AuditLog.entity_id == s.patient_id))).order_by(AuditLog.id).all()
        out["audit"] = [{"id": a.id, "entity": a.entity, "action": a.action, "old_value": a.old_value,
                         "new_value": a.new_value, "created_at": iso(a.created_at),
                         "actor": db.get(User, a.actor_id).name} for a in entries]
    return out


def _summary_out(row: AISummary | None):
    return {"status": "ok", "en": row.en, "hi": row.hi, "cached": True} if row else None


@router.post("/screenings", status_code=201)
def submit_screening(body: ScreeningIn, response: Response, user: User = Depends(current_user),
                     db: Session = Depends(get_db)):
    # Retry safety: the same client_uuid always returns the same screening, never a second one.
    existing = db.query(Screening).filter(Screening.client_uuid == body.client_uuid).first()
    if existing:
        return _replay(db, existing, user, response)

    patient = get_patient_or_404(db, user, body.patient_id)
    today = today_ist()
    age = age_on(patient.dob, today)
    result = run(age, patient.sex, body.answers)
    if result["errors"]:
        raise HTTPException(422, {"message": "Some answers are missing or invalid", "errors": result["errors"]})

    s = Screening(
        client_uuid=body.client_uuid, patient_id=patient.id, created_by=user.id,
        form_version=get_config()["version"], screened_on=today, dob_at_screening=patient.dob,
        age_at_screening=age, sex_at_screening=patient.sex, answers=result["answers"],
        discarded_answers=result["discarded"], score=result["score"], risk_level=result["level"],
        risk_reasons=result["reasons"], final_level=result["level"],
    )
    db.add(s)
    try:
        db.flush()
        audit(db, user, "screening", s.id, "submit", None,
              {"risk_level": s.risk_level, "score": s.score, "discarded": list(s.discarded_answers)})
        db.commit()
    except IntegrityError:  # two retries raced; the other one won
        db.rollback()
        existing = db.query(Screening).filter(Screening.client_uuid == body.client_uuid).first()
        if not existing:
            raise
        return _replay(db, existing, user, response)
    return detail(db, s, user)


def _replay(db, existing, user, response):
    if existing.created_by != user.id:
        raise HTTPException(409, "This screening id is already used")
    response.status_code = 200
    return detail(db, existing, user)


@router.get("/screenings")
def list_screenings(risk: Level | None = None, reviewed: bool | None = None, patient_id: int | None = None,
                    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                    user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = visible_screenings(db, user)
    if risk:
        q = q.filter(Screening.final_level == risk)
    if reviewed is not None:
        q = q.filter(Screening.review_decision.is_not(None) if reviewed else Screening.review_decision.is_(None))
    if patient_id:
        q = q.filter(Screening.patient_id == patient_id)
    total = q.count()
    rows = (q.add_entity(Patient).order_by(Screening.created_at.desc(), Screening.id.desc())
            .offset((page - 1) * page_size).limit(page_size).all())
    return {"items": [list_item(s, p) for s, p in rows], "total": total, "page": page, "page_size": page_size,
            "pages": max(1, -(-total // page_size))}


@router.get("/screenings/{screening_id}")
def get_screening(screening_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return detail(db, get_screening_or_404(db, user, screening_id), user)


@router.post("/screenings/{screening_id}/review")
def review_screening(screening_id: int, body: ReviewIn, user: User = Depends(require_doctor),
                     db: Session = Depends(get_db)):
    s = get_screening_or_404(db, user, screening_id)
    previous = s.final_level
    if body.decision == "override":
        if not body.reason:
            raise HTTPException(422, "Please give a reason for overriding the risk level")
        if len(body.reason) < 5:
            raise HTTPException(422, "The reason is too short to be useful")
        if not body.final_level:
            raise HTTPException(422, "Choose the new risk level")
        if body.final_level == previous:
            raise HTTPException(422, f"The risk level is already {previous}. Choose a different level to override.")
        final = body.final_level
    else:
        final = s.risk_level  # accepting means agreeing with the system's result

    old_review = s.review_decision
    db.add(Review(screening_id=s.id, doctor_id=user.id, decision=body.decision, previous_level=previous,
                  final_level=final, reason=body.reason))
    s.final_level, s.review_decision = final, body.decision
    audit(db, user, "screening", s.id, f"review_{body.decision}",
          {"final_level": previous, "review_decision": old_review},
          {"final_level": final, "review_decision": body.decision, "reason": body.reason})
    db.commit()  # review row, screening update and audit row commit together
    return detail(db, s, user)


@router.post("/screenings/{screening_id}/summary")
def screening_summary(screening_id: int, refresh: bool = False, user: User = Depends(require_doctor),
                      db: Session = Depends(get_db)):
    """Always answers 200. If the AI is down the doctor still has the full result; only this box is unavailable."""
    s = get_screening_or_404(db, user, screening_id)
    row = db.query(AISummary).filter(AISummary.screening_id == s.id).first()
    if row and not refresh:
        return _summary_out(row)
    result = ai.generate_summary(
        age=s.age_at_screening, sex=s.sex_at_screening, level=s.risk_level, score=s.score,
        reasons=[r["text"] for r in s.risk_reasons], answers=describe_answers(get_config(), s.answers))
    if result is None:
        return {"status": "unavailable", "message": ai.UNAVAILABLE}
    if row:
        row.en, row.hi, row.model = result.en, result.hi, ai.model_name()
    else:
        db.add(AISummary(screening_id=s.id, en=result.en, hi=result.hi, model=ai.model_name()))
    db.commit()
    return {"status": "ok", "en": result.en, "hi": result.hi, "cached": False}


@router.get("/audit")
def audit_log(entity: str, entity_id: int, user: User = Depends(require_doctor), db: Session = Depends(get_db)):
    rows = db.query(AuditLog).filter(AuditLog.entity == entity, AuditLog.entity_id == entity_id).order_by(AuditLog.id).all()
    return [{"id": a.id, "action": a.action, "old_value": a.old_value, "new_value": a.new_value,
             "created_at": iso(a.created_at), "actor": db.get(User, a.actor_id).name} for a in rows]
