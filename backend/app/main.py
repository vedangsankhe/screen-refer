from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import CORS_ORIGINS, SEED_PASSWORD
from .database import Base, SessionLocal, engine
from .models import User
from .routers import auth, patients, screenings
from .security import hash_password


def seed_users():
    """Creates the test logins on first start (only if there are no users yet)."""
    with SessionLocal() as db:
        if db.query(User).count():
            return
        for email, name, role in [("worker1@example.com", "Asha (health worker)", "worker"),
                                  ("worker2@example.com", "Meena (health worker)", "worker"),
                                  ("doctor@example.com", "Dr. Rao", "doctor")]:
            db.add(User(email=email, name=name, role=role, password_hash=hash_password(SEED_PASSWORD)))
        db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)  # simple for this size; a real project would use Alembic migrations
    seed_users()
    yield


app = FastAPI(title="Screen & Refer API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])
app.include_router(auth.router)
app.include_router(patients.router)
app.include_router(screenings.router)


@app.get("/health")
def health():
    return {"ok": True}
