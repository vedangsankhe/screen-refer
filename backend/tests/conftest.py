import os
import sys
from pathlib import Path

# Must be set before the app is imported
os.environ["DATABASE_URL"] = "sqlite:///./test_screen_refer.db"
os.environ["LLM_API_KEY"] = ""
os.environ["SEED_PASSWORD"] = "Test@1234"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app

PASSWORD = "Test@1234"


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    with TestClient(app) as c:  # entering the context runs startup: create tables + seed users
        yield c


def login(client, who):
    r = client.post("/auth/login", json={"email": f"{who}@example.com", "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture()
def worker1(client): return login(client, "worker1")
@pytest.fixture()
def worker2(client): return login(client, "worker2")
@pytest.fixture()
def doctor(client): return login(client, "doctor")


def make_patient(client, headers, name="Rahul Sharma", dob="1990-05-10", sex="male", phone="9876543210", **extra):
    return client.post("/patients", json={"name": name, "dob": dob, "sex": sex, "phone": phone, **extra}, headers=headers)


def dob_for_age(years: int) -> str:
    from app.access import today_ist
    t = today_ist()
    return t.replace(year=t.year - years, day=1 if t.month == 2 and t.day == 29 else t.day).isoformat()
