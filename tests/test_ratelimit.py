"""Rate limit tests for LifeLink."""

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
    # reset rate limit buckets
    from routes import middleware
    middleware._buckets.clear()
    app = create_app()
    app.config["TESTING"] = True
    with app.app_context():
        db.drop_all()
        db.create_all()
    with app.test_client() as c:
        yield c


def test_rate_limit_allows_normal(client):
    r = client.get("/health")
    assert r.status_code == 200


def test_rate_limit_exceeds(client):
    # POST limit is 10/min; send 15
    for i in range(12):
        client.post("/api/auth/login", json={"email": f"u{i}@x.com", "password": "x"})
    r = client.post("/api/auth/login", json={"email": "extra@x.com", "password": "x"})
    assert r.status_code == 429
    assert "Rate limit" in r.get_json()["error"]


def test_rate_limit_resets_per_ip(client):
    # different X-Forwarded-For -> separate bucket
    for i in range(12):
        client.post("/api/auth/login", json={"email": f"u{i}@x.com", "password": "x"}, headers={"X-Forwarded-For": "1.1.1.1"})
    r = client.post("/api/auth/login", json={"email": "x@x.com", "password": "x"}, headers={"X-Forwarded-For": "2.2.2.2"})
    assert r.status_code != 429


def test_cors_headers_present(client):
    r = client.get("/health", headers={"Origin": "http://example.com"})
    # CORS_ORIGINS empty -> allow any origin
    assert "Access-Control-Allow-Origin" in r.headers
