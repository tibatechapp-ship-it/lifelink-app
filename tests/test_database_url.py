"""The URL contract: one place turns a platform URL into a drivable one.

These are the pure rules, so they run anywhere (no Flask, no crypto extension):
managed platforms hand out `postgres://`, SQLAlchemy 2 dropped that alias, and
`postgresql://` would select psycopg2 — which this project does not install.
"""

from __future__ import annotations

import pytest

from models.database import (
    database_uri,
    engine_options,
    migration_engine_options,
    normalize_database_url,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # platform aliases →
        ("postgres://u:p@db:5432/lifelink", "postgresql+psycopg://u:p@db:5432/lifelink"),
        ("postgresql://u:p@db:5432/lifelink", "postgresql+psycopg://u:p@db:5432/lifelink"),
        # an explicitly chosen driver is respected
        ("postgresql+psycopg2://u:p@db/lifelink", "postgresql+psycopg2://u:p@db/lifelink"),
        ("postgresql+psycopg://u:p@db/lifelink", "postgresql+psycopg://u:p@db/lifelink"),
        # sqlite untouched (tests + local dev)
        ("sqlite:///tmp/x.db", "sqlite:///tmp/x.db"),
        ("sqlite:///:memory:", "sqlite:///:memory:"),
    ],
)
def test_normalize_database_url(raw: str, expected: str) -> None:
    assert normalize_database_url(raw) == expected


def test_database_uri_uses_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@db:5432/app")
    assert database_uri("/tmp/fallback.db") == "postgresql+psycopg://u:p@db:5432/app"


def test_database_uri_falls_back_to_sqlite(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert database_uri("/tmp/fallback.db") == "sqlite:////tmp/fallback.db"


def test_blank_database_url_is_treated_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "   ")
    assert database_uri("/tmp/fallback.db").startswith("sqlite:///")


def test_network_databases_get_a_pre_ping_pool() -> None:
    options = engine_options("postgresql+psycopg://u:p@db/app")
    assert options["pool_pre_ping"] is True
    assert options["pool_recycle"] == 1800


def test_sqlite_needs_no_pool_options() -> None:
    assert engine_options("sqlite:///tmp/x.db") == {}


def test_migration_options_fit_a_null_pool() -> None:
    """Alembic uses NullPool, which has no pool to size (TypeError otherwise)."""
    options = migration_engine_options("postgresql+psycopg://u:p@db/app")
    assert options == {"pool_pre_ping": True}
    assert engine_options("postgresql+psycopg://u:p@db/app")["pool_size"] == 5
    assert migration_engine_options("sqlite:///tmp/x.db") == {}
