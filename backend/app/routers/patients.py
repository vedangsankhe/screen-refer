from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..access import audit, get_patient_or_404, iso, today_ist, visible_patients
from ..database import get_db
from ..models import Patient, Screening, User, utcnow
from ..security import current_user
from ..services.engine import run
from ..services.normalize import clean_name, digits_of, name_key, name_similarity, normalize_phone
from ..services.visibility import age_on

router = APIRouter(prefix="/patients", tags=["patients"])
DUPLICATE_NAME_SCORE = 80


def _check_dob(v: date | None) -> date | None:
    if v is not None and not (date(1900, 1, 1) <= v <= today_ist()):
        raise ValueError("Date of birth must be between 1900 and today")
    return v


class PatientIn(BaseModel):
    name: str = Field(max_length=200)
    dob: date
    sex: Literal["male", "female", "other"]
    phone: str
    force_create: bool = False  # "this really is a different person"

    _dob = field_validator("dob")(_check_dob)

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v):
        v = clean_name(v)
        if not v:
            raise ValueError("Name is required")
        return v


class PatientPatch(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    dob: date | None = None
    sex: Literal["male", "female", "other"] | None = None
    phone: str | None = None
    force_create: bool = False

    _dob = field_validator("dob")(_check_dob)


def patient_out(p: Patient, users: dict | None = None) -> dict:
    return {
        "id": p.id, "name": p.name, "dob": p.dob.isoformat(), "sex": p.sex, "phone": p.phone,
        "age": age_on(p.dob, today_ist()), "created_by": p.created_by,
        "created_by_name": (users or {}).get(p.created_by),
        "created_at": iso(p.created_at), "updated_at": iso(p.updated_at),
    }


def _phone_or_422(raw: str) -> str:
    try:
        return normalize_phone(raw)
    except ValueError as e:
        raise HTTPException(422, str(e))


def _check_duplicates(db: Session, user: User, phone: str, name: str, dob: date, exclude_id: int | None):
    """Same phone + (similar name OR same date of birth) = probably the same person.
    Families share phones, so this is a warning (409) the user can override, not a hard block.
    Matches that belong to other health workers are counted but their details are not shown."""
    q = db.query(Patient).filter(Patient.phone == phone, Patient.deleted_at.is_(None))
    if exclude_id:
        q = q.filter(Patient.id != exclude_id)
    visible, hidden = [], 0
    for other in q.all():
        sim = name_similarity(name, other.name)
        if sim >= DUPLICATE_NAME_SCORE or other.dob == dob:
            if user.role == "doctor" or other.created_by == user.id:
                visible.append({**patient_out(other), "similarity": sim})
            else:
                hidden += 1
    if visible or hidden:
        raise HTTPException(409, {
            "code": "possible_duplicate",
            "message": "This person may already be registered.",
            "candidates": visible,
            "hidden_matches": hidden,
        })


@router.post("", status_code=201)
def create_patient(body: PatientIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    phone = _phone_or_422(body.phone)
    if not body.force_create:
        _check_duplicates(db, user, phone, body.name, body.dob, None)
    p = Patient(name=body.name, name_key=name_key(body.name), dob=body.dob, sex=body.sex, phone=phone,
                created_by=user.id)
    db.add(p)
    db.flush()  # gives p an id so the audit row can point at it
    audit(db, user, "patient", p.id, "create", None, {"name": p.name, "dob": p.dob.isoformat(), "sex": p.sex, "phone": p.phone})
    db.commit()
    return patient_out(p)


@router.get("")
def list_patients(q: str = "", page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                  user: User = Depends(current_user), db: Session = Depends(get_db)):
    query = visible_patients(db, user)
    q = q.strip()
    if q:
        conds = [func.lower(Patient.name).contains(q.lower(), autoescape=True)]
        key = name_key(q)
        if len(key) >= 2:
            conds.append(Patient.name_key.contains(key, autoescape=True))  # "rahul" finds "राहुल"
        digits = digits_of(q)
        if len(digits) >= 3:
            conds.append(Patient.phone.contains(digits[-10:] if len(digits) > 10 else digits))
        query = query.filter(or_(*conds))
    total = query.count()
    rows = query.order_by(Patient.created_at.desc(), Patient.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    users = {u.id: u.name for u in db.query(User).filter(User.id.in_({r.created_by for r in rows}))} if rows else {}
    return {"items": [patient_out(r, users) for r in rows], "total": total, "page": page,
            "page_size": page_size, "pages": max(1, -(-total // page_size))}


@router.get("/{patient_id}")
def get_patient(patient_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return patient_out(get_patient_or_404(db, user, patient_id))


@router.patch("/{patient_id}")
def update_patient(patient_id: int, body: PatientPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = get_patient_or_404(db, user, patient_id)
    new = {}
    if body.name is not None:
        new["name"] = clean_name(body.name)
        if not new["name"]:
            raise HTTPException(422, "Name is required")
    if body.dob is not None:
        new["dob"] = body.dob
    if body.sex is not None:
        new["sex"] = body.sex
    if body.phone is not None:
        new["phone"] = _phone_or_422(body.phone)
    changes = {k: v for k, v in new.items() if v != getattr(p, k)}
    if not changes:
        return patient_out(p)

    if ("name" in changes or "phone" in changes) and not body.force_create:
        _check_duplicates(db, user, changes.get("phone", p.phone), changes.get("name", p.name),
                          changes.get("dob", p.dob), p.id)

    old_vals = {k: (getattr(p, k).isoformat() if isinstance(getattr(p, k), date) else getattr(p, k)) for k in changes}
    new_vals = {k: (v.isoformat() if isinstance(v, date) else v) for k, v in changes.items()}
    for k, v in changes.items():
        setattr(p, k, v)
    if "name" in changes:
        p.name_key = name_key(p.name)
    audit(db, user, "patient", p.id, "update", old_vals, new_vals)

    if "dob" in changes or "sex" in changes:
        _reevaluate_screenings(db, user, p)
    db.commit()
    return patient_out(p)


def _reevaluate_screenings(db: Session, user: User, p: Patient):
    """DOB or sex was corrected. Old screenings keep their original result (it is what the worker
    actually saw), but we re-run branching + scoring with the corrected values and attach the outcome
    so the doctor sees a clear 'needs re-screening' warning."""
    for s in db.query(Screening).filter(Screening.patient_id == p.id).all():
        new_age = age_on(p.dob, s.screened_on)
        if new_age == s.age_at_screening and p.sex == s.sex_at_screening:
            s.reevaluation = None  # corrected back to what it was, or the change doesn't matter
            continue
        result = run(new_age, p.sex, s.answers)
        unanswered = [qid for qid in result["visible"] if qid not in s.answers]
        info = {
            "old_dob": s.dob_at_screening.isoformat(), "new_dob": p.dob.isoformat(),
            "old_age": s.age_at_screening, "new_age": new_age,
            "old_sex": s.sex_at_screening, "new_sex": p.sex,
            "original_level": s.risk_level, "recomputed_level": result["level"],
            "recomputed_score": result["score"],
            "ignored_answers": list(result["discarded"].keys()),   # answered, but not relevant at the new age/sex
            "unanswered_questions": unanswered,                    # relevant at the new age/sex, never asked
            "needs_rescreen": bool(unanswered) or result["level"] != s.risk_level,
            "flagged_at": utcnow().isoformat(),
        }
        s.reevaluation = info
        audit(db, user, "screening", s.id, "flagged_for_reevaluation", {"age": s.age_at_screening, "sex": s.sex_at_screening},
              {"age": new_age, "sex": p.sex, "recomputed_level": result["level"]})


@router.delete("/{patient_id}")
def delete_patient(patient_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = get_patient_or_404(db, user, patient_id)
    p.deleted_at = utcnow()  # soft delete: the row and its screenings stay in the database
    audit(db, user, "patient", p.id, "soft_delete", {"deleted": False}, {"deleted": True})
    db.commit()
    return {"ok": True}
