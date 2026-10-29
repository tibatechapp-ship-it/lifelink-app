"""trigram indexes for ILIKE city search

Revision ID: a1f2c3d4e5b6
Revises: 0fabda7ade84
Create Date: 2026-10-30

Why: both search endpoints filter cities with ``ILIKE '%<city>%'`` (leading
wildcard). A B-tree index — including the existing composite
``ix_donors_blood_city_avail`` / ``ix_emerg_blood_city_status`` — cannot serve
a leading-wildcard pattern, so every city filter was a sequential scan. A
GIN trigram index on ``lower(city)`` makes exactly that pattern index-backed
without touching the query or its substring semantics.

Dialect safety: this is a no-op outside PostgreSQL (sqlite dev/tests keep
running through ``create_all`` and never see this migration). On PostgreSQL,
``CREATE EXTENSION pg_trgm`` is attempted; on hosts that lock extensions down
the migration logs a warning and continues — the app keeps working, the city
filter just stays unindexed until the operator grants the extension.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1f2c3d4e5b6'
down_revision: Union[str, Sequence[str], None] = '0fabda7ade84'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEXES = (
    ("ix_donors_city_trgm", "donors", "lower(city) gin_trgm_ops"),
    ("ix_emerg_city_trgm", "emergency_requests", "lower(city) gin_trgm_ops"),
)


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    """Add GIN trigram indexes for the ILIKE city filters (PostgreSQL only)."""
    if not _is_postgres():
        return
    try:
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    except Exception as exc:  # noqa: BLE001 - extension grants are host-specific
        print(f"[a1f2c3d4e5b6] WARNING: pg_trgm unavailable ({exc}); "
              "city ILIKE search stays unindexed. Grant pg_trgm and re-run "
              "`alembic upgrade head` to pick the indexes up.")
        return
    for name, table, expr in _INDEXES:
        op.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table} USING gin ({expr})")


def downgrade() -> None:
    """Drop the trigram indexes (the extension itself is left installed)."""
    if not _is_postgres():
        return
    for name, _table, _expr in _INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {name}")
