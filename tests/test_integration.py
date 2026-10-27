"""Integration tests for LifeLink (end-to-end flow)."""

import os

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("FLASK_DEBUG", "0")

from app import create_app
from models.models import db


@pytest.fixture
def client(tmp_path, monkeypatch):
    dbfile = str(tmp_path / "test.db")
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{dbfile}")
    monkeypatch.setenv("LIFELINK_DB_PATH", dbfile)
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    monkeypatch.setenv("FIELD_ENCRYPTION_KEY", "integration-test-key-32bytes!!!!")
    from routes import middleware
    middleware._buckets.clear()
    app = create_app()
    app.config["TESTING"] = True
    with app.app_context():
        db.drop_all()
        db.create_all()
    with app.test_client() as c:
        yield c, dbfile


def test_full_donor_flow(client):
    c, dbfile = client
    # register
    r = c.post("/api/auth/register", json={
        "name": "Ali", "email": "ali@test.com", "phone": "+967700000000",
        "blood_type": "O+", "city": "Sanaa", "age": 25, "weight": 70, "password": "secret123",
    })
    assert r.status_code == 201
    token = r.get_json()["access_token"]

    # create donor
    r = c.post("/api/donors", headers={"Authorization": f"Bearer {token}"}, json={
        "name": "Bob", "email": "bob@test.com", "phone": "+967700000001",
        "blood_type": "A+", "city": "Aden", "age": 30, "weight": 75,
    })
    assert r.status_code == 201
    donor_id = r.get_json()["id"]

    # list
    r = c.get("/api/donors", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.get_json()["count"] >= 1

    # get
    r = c.get(f"/api/donors/{donor_id}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.get_json()["name"] == "Bob"

    # update (own record — donor id 1 is Ali, but donor_id 2 is Bob; update Bob as admin? no. Update own=Ali id=1)
    r = c.put("/api/donors/1", headers={"Authorization": f"Bearer {token}"}, json={"city": "Taiz"})
    assert r.status_code == 200
    assert r.get_json()["city"] == "Taiz"

    # delete Bob (id=2) — Ali is donor, cannot delete others -> 403 (expected)
    r = c.delete(f"/api/donors/{donor_id}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_pii_encrypted_at_rest(client):
    c, dbfile = client
    r = c.post("/api/auth/register", json={
        "name": "Ali", "email": "ali@test.com", "phone": "+967700000000",
        "blood_type": "O+", "city": "Sanaa", "age": 25, "weight": 70, "password": "secret123",
    })
    _ = r.get_json()["access_token"]
    import sqlite3
    conn = sqlite3.connect(dbfile)
    rows = conn.execute("SELECT name, phone FROM donors").fetchall()
    conn.close()
    for name, phone in rows:
        assert "Ali" not in str(name), "name not encrypted at rest"
        assert "+967" not in str(phone), "phone not encrypted at rest"


def test_emergency_flow(client):
    c, dbfile = client
    r = c.post("/api/auth/register", json={
        "name": "Ali", "email": "ali@test.com", "phone": "+967700000000",
        "blood_type": "O+", "city": "Sanaa", "age": 25, "weight": 70, "password": "secret123",
    })
    token = r.get_json()["access_token"]
    r = c.post("/api/emergencies", headers={"Authorization": f"Bearer {token}"}, json={
        "patient_name": "Patient X", "blood_type": "O+", "hospital": "City Hosp",
        "city": "Sanaa", "contact_phone": "+967700000001", "urgency": "critical",
    })
    assert r.status_code == 201
    eid = r.get_json()["id"]
    r = c.get(f"/api/emergencies/{eid}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.get_json()["patient_name"] == "Patient X"
    # verify encrypted at rest
    import sqlite3
    conn = sqlite3.connect(dbfile)
    row = conn.execute("SELECT patient_name, contact_phone FROM emergency_requests WHERE id=?", (eid,)).fetchone()
    conn.close()
    assert "Patient X" not in str(row[0])
    assert "+967" not in str(row[1])


def test_health_endpoint(client):
    c, dbfile = client
    r = c.get("/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"
