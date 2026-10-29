"""Alembic environment for LifeLink.

The URL is resolved by the SAME code the app uses (``models.database``), so a
migration can never run against a different database than the one the app
reads — the classic deploy failure where migrations "succeed" into a database
nobody is using.

Only the schema metadata is imported here (not ``create_app``): building
migration context must not boot Flask, open sockets or create tables.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make the project root importable when alembic runs from elsewhere (inside the
# container, `alembic` is invoked from /app, but a CI step may not be).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.database import database_uri, migration_engine_options
from models.models import db

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = db.metadata

# The app's URL wins; alembic.ini deliberately carries no sqlalchemy.url so a
# committed file can never point at a stale/local database by accident.
_base_dir = str(Path(__file__).resolve().parent.parent)
_url = database_uri(os.path.join(_base_dir, "lifelink.db"))
config.set_main_option("sqlalchemy.url", _url.replace("%", "%%"))


def run_migrations_offline() -> None:
    """Emit SQL instead of running it (``alembic upgrade head --sql``)."""
    context.configure(
        url=_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_as_batch=_url.startswith("sqlite"),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations to the real database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        **migration_engine_options(_url),
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            # SQLite cannot ALTER most things in place; batch mode rewrites the
            # table instead. Harmless (and unused) on Postgres.
            render_as_batch=_url.startswith("sqlite"),
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
