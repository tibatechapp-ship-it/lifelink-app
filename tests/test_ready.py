"""Liveness vs readiness.

/health answers "the process is up" and must not touch the database: a
healthcheck that needs Postgres turns a database outage into a restart loop.
/ready answers "may traffic be sent here" and returns 503 with the reason when
the database is unreachable. Both bodies keep the same shape so a failing
rollout is readable from a single log line.
"""

from __future__ import annotations

import pytest

from app import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'ready.db'}")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    monkeypatch.setenv("FIELD_ENCRYPTION_KEY", "ready-test-key-32-bytes-long!!!!!")
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_health_is_dependency_free(client):
    body = client.get("/health").get_json()
    assert body == {"status": "ok", "service": "lifelink", "version": "1.0.0"}


def test_ready_is_200_when_the_database_answers(client):
    r = client.get("/ready")
    body = r.get_json()
    assert r.status_code == 200
    assert body["ready"] is True
    assert body["status"] == "ready"
    assert body["checks"][0]["name"] == "database"
    assert body["checks"][0]["ok"] is True


def test_ready_body_shape_is_identical_on_failure(tmp_path, monkeypatch):
    # A directory that cannot exist → the engine cannot even open a connection.
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("DATABASE_URL", "sqlite:////nonexistent-dir/never/ready.db")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    monkeypatch.setenv("FIELD_ENCRYPTION_KEY", "ready-test-key-32-bytes-long!!!!!")
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        r = c.get("/ready")
        body = r.get_json()
    assert r.status_code == 503
    assert body["ready"] is False
    assert body["status"] == "not_ready"
    assert {"ready", "status", "version", "checks", "latency_ms"} <= set(body)
    assert body["checks"][0]["ok"] is False
    assert body["checks"][0]["error"]


def test_postgres_schema_is_owned_by_alembic_not_create_all(tmp_path, monkeypatch):
    """create_all() must never run against Postgres.

    It would create missing tables silently, so a container that skipped
    `alembic upgrade head` would answer /ready with an outdated schema.
    """
    pytest.importorskip("psycopg", reason="psycopg is installed in CI/deploy only")
    from models.models import db

    calls: list[str] = []
    monkeypatch.setattr(db, "create_all", lambda *a, **k: calls.append("create_all"))
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@127.0.0.1:5432/lifelink")
    app = create_app()
    assert app.config["SQLALCHEMY_DATABASE_URI"] == "postgresql+psycopg://u:p@127.0.0.1:5432/lifelink"
    assert calls == []
