"""geo coordinates for emergency-donor matching

Revision ID: c7d1e5f9a3b2
Revises: a1f2c3d4e5b6
Create Date: 2026-10-31

Why: Week-1 of the productization plan adds geographic donor matching —
"compatible blood type x nearest x last donation safe". Donors and emergency
requests gain optional latitude/longitude columns. Both stay nullable: the
match service falls back to the existing same-city semantics when coordinates
are absent, so nothing breaks for existing rows.

Dialect safety: plain ``ADD COLUMN`` / ``DROP COLUMN`` — identical on SQLite
(dev/tests) and PostgreSQL (CI deploy proof).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c7d1e5f9a3b2'
down_revision: Union[str, Sequence[str], None] = 'a1f2c3d4e5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = (
    ('donors', 'latitude'),
    ('donors', 'longitude'),
    ('emergency_requests', 'latitude'),
    ('emergency_requests', 'longitude'),
)


def upgrade() -> None:
    """Add optional latitude/longitude to donors and emergency_requests."""
    for table, column in _COLUMNS:
        op.add_column(table, sa.Column(column, sa.Float(), nullable=True))


def downgrade() -> None:
    """Remove the geographic columns (reverse order of upgrade)."""
    for table, column in reversed(_COLUMNS):
        op.drop_column(table, column)
