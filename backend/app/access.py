"""The ONLY place that decides which rows a user may see. Every route goes through these helpers,
so a worker can never reach another worker's data by guessing an id (they get a 404)."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import AuditLog, Patient, Screening, User

IST = ZoneInfo("Asia/Kolkata")


def today_ist() -> date:
    return datetime.now(IST).date()


def visible_patients(db: Session, user: User):
    q = db.query(Patient).filter(Patient.deleted_at.is_(None))
    return q if user.role == "doctor" else q.filter(Patient.created_by == user.id)


def visible_screenings(db: Session, user: User):
    q = db.query(Screening).join(Patient, Patient.id == Screening.patient_id).filter(Patient.deleted_at.is_(None))
    return q if user.role == "doctor" else q.filter(Screening.created_by == user.id)


def get_patient_or_404(db: Session, user: User, patient_id: int) -> Patient:
    p = visible_patients(db, user).filter(Patient.id == patient_id).first()
    if not p:
        raise HTTPException(404, "Patient not found")
    return p


def get_screening_or_404(db: Session, user: User, screening_id: int) -> Screening:
    s = visible_screenings(db, user).filter(Screening.id == screening_id).first()
    if not s:
        raise HTTPException(404, "Screening not found")
    return s


def iso(dt):
    """Datetimes come back naive from SQLite; always send them as UTC with a Z."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def audit(db: Session, actor: User, entity: str, entity_id: int, action: str, old=None, new=None):
    """Adds an audit row to the CURRENT transaction; the caller commits, so change + log succeed or fail together."""
    db.add(AuditLog(actor_id=actor.id, entity=entity, entity_id=entity_id, action=action, old_value=old, new_value=new))
