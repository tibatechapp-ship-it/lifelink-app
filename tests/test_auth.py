"""Auth tests for LifeLink."""

import os
import pytest

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("FLASK_DEBUG", "0")

from app import create_app
from models.models import db, Donor


@pytest.fixture
def client(tmp_path, monkeypatch):
    dbfile = str(tmp_path / "test.db")
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{dbfile}")
    monkeypatch.setenv("LIFELINK_DB_PATH", dbfile)
    app = create_app()
    app.config["TESTING"] = True
    with app.app_context():
        db.drop_all()
        db.create_all()
    with app.test_client() as c:
        yield c


def _register(client, email="a@b.com", password="secret123", role="donor"):
    return client.post("/api/auth/register", json={
        "name": "Ali", "email": email, "phone": "+967700000000",
        "blood_type": "O+", "city": "Sanaa", "age": 25, "weight": 70.0,
        "password": password, "role": role,
    })


def test_register_success(client):
    r = _register(client)
    assert r.status_code == 201
    data = r.get_json()
    assert "access_token" in data and "refresh_token" in data
    assert data["donor"]["email"] == "a@b.com"


def test_register_duplicate_email(client):
    _register(client)
    r = _register(client)
    assert r.status_code == 409


def test_register_missing_fields(client):
    r = client.post("/api/auth/register", json={"email": "x@y.com"})
    assert r.status_code == 400
    assert "Missing fields" in r.get_json()["error"]


def test_register_invalid_role_ignored(client):
    # self-registration ignores role param -> always donor
    r = _register(client, role="superadmin")
    assert r.status_code == 201
    assert r.get_json()["donor"]["role"] == "donor"


def test_login_success(client):
    _register(client)
    r = client.post("/api/auth/login", json={"email": "a@b.com", "password": "secret123"})
    assert r.status_code == 200
    assert "access_token" in r.get_json()


def test_login_wrong_password(client):
    _register(client)
    r = client.post("/api/auth/login", json={"email": "a@b.com", "password": "wrong"})
    assert r.status_code == 401


def test_login_unknown_email(client):
    r = client.post("/api/auth/login", json={"email": "nope@x.com", "password": "x"})
    assert r.status_code == 401


def test_protected_route_no_token(client):
    r = client.post("/api/donors", json={"name": "x"})
    assert r.status_code == 401


def test_protected_route_with_token(client):
    _register(client)
    login = client.post("/api/auth/login", json={"email": "a@b.com", "password": "secret123"})
    token = login.get_json()["access_token"]
    r = client.post("/api/donors", headers={"Authorization": f"Bearer {token}"}, json={
        "name": "Bob", "email": "bob@b.com", "phone": "+967700000001",
        "blood_type": "A+", "city": "Aden", "age": 30, "weight": 75,
    })
    assert r.status_code == 201


def test_me_endpoint(client):
    _register(client)
    login = client.post("/api/auth/login", json={"email": "a@b.com", "password": "secret123"})
    token = login.get_json()["access_token"]
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.get_json()["email"] == "a@b.com"


def test_refresh_token(client):
    _register(client)
    login = client.post("/api/auth/login", json={"email": "a@b.com", "password": "secret123"})
    refresh = login.get_json()["refresh_token"]
    r = client.post("/api/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 200
    assert "access_token" in r.get_json()


def test_authorization_donor_cannot_delete_others(client):
    _register(client, email="a@b.com")
    _register(client, email="b@b.com")
    # login as b
    login = client.post("/api/auth/login", json={"email": "b@b.com", "password": "secret123"})
    token = login.get_json()["access_token"]
    # try to delete donor 1 (a) as b -> forbidden
    r = client.delete("/api/donors/1", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_get_donor_without_token(client):
    r = client.get("/api/donors/1")
    assert r.status_code == 401


def test_tampered_token_rejected(client):
    _register(client)
    r = client.get("/api/donors/1", headers={"Authorization": "Bearer tampered.garbage.token"})
    assert r.status_code == 401


def test_emergency_create_requires_auth(client):
    r = client.post("/api/emergencies", json={
        "patient_name": "X", "blood_type": "O+", "hospital": "H", "city": "C", "contact_phone": "+967700000000",
    })
    assert r.status_code == 401


def test_emergency_create_with_token(client):
    _register(client)
    login = client.post("/api/auth/login", json={"email": "a@b.com", "password": "secret123"})
    token = login.get_json()["access_token"]
    r = client.post("/api/emergencies", headers={"Authorization": f"Bearer {token}"}, json={
        "patient_name": "X", "blood_type": "O+", "hospital": "H", "city": "C", "contact_phone": "+967700000000",
    })
    assert r.status_code == 201


def test_role_escalation_blocked(client):
    # self-registration cannot elevate to admin
    r = _register(client, role="admin")
    assert r.status_code == 201
    assert r.get_json()["donor"]["role"] == "donor"
