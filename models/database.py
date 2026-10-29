"""Database URL handling shared by the app and the migration environment.

One rule, one place: whatever runs against the database (Flask in production and
Alembic during a deploy) must resolve the SAME URL. A drift here is the classic
"migrations ran against one database, the app reads another" failure.

The ``postgres://`` → ``postgresql+psycopg://`` rewrite matters because managed
platforms (Render, Heroku, Railway) hand out ``postgres://`` URLs. SQLAlchemy 2
dropped that alias, and the bare ``postgresql://`` would pick psycopg2 — which
this project does not install. Normalising here means a copied dashboard URL
just works.
"""

from __future__ import annotations

import os
from typing import Final

DEFAULT_PORT_DRIVER: Final = "psycopg"


def normalize_database_url(url: str) -> str:
    """Return a SQLAlchemy-2 URL this project can actually drive.

    * ``postgres://…``      → ``postgresql+psycopg://…`` (platform alias, dropped in SA2)
    * ``postgresql://…``    → ``postgresql+psycopg://…`` (pin the psycopg3 driver)
    * ``postgresql+psycopg2://…`` → kept, the operator asked for it explicitly
    * ``sqlite://``         → untouched (tests and local dev)
    """
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return f"postgresql+{DEFAULT_PORT_DRIVER}://" + url[len("postgresql://"):]
    return url


def database_uri(default_sqlite_path: str) -> str:
    """The configured database, or a local SQLite file when nothing is set."""
    configured = os.environ.get("DATABASE_URL", "").strip()
    if configured:
        return normalize_database_url(configured)
    return f"sqlite:///{default_sqlite_path}"


def engine_options(uri: str) -> dict[str, object]:
    """Pool options that survive a real network database.

    ``pool_pre_ping`` avoids handing out connections a restarted Postgres has
    already dropped (the "server closed the connection unexpectedly" class of
    error), and the short recycle keeps connections inside a platform's idle
    timeout. SQLite needs neither.
    """
    if not uri.startswith("sqlite"):
        return {"pool_pre_ping": True, "pool_recycle": 1800, "pool_size": 5, "max_overflow": 10}
    return {}


def migration_engine_options(uri: str) -> dict[str, object]:
    """Pool options Alembic may use.

    Migrations run in a short-lived process that closes its single connection
    when it exits, so the environment configures ``NullPool``. ``NullPool`` has
    no pool to size — passing ``pool_size``/``max_overflow`` raises
    ``TypeError: Invalid argument(s) 'pool_size','max_overflow'`` — so only
    ``pool_pre_ping`` survives here.
    """
    if uri.startswith("sqlite"):
        return {}
    return {"pool_pre_ping": True}
