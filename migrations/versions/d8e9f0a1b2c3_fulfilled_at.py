"""fulfilled_at على النداءات — زمن استجابة قابل للقياس للمشغّل

Revision ID: d8e9f0a1b2c3
Revises: c7d1e5f9a3b2
Create Date: 2026-10-31

Why: Week-2 of the productization plan adds operator statistics
(`/admin/stats`: نداءات، فصائل مطلوبة، زمن استجابة متوسط). Measuring
response time honestly needs a timestamp on the moment a request is marked
"fulfilled" — it cannot be derived from `status` alone. The column stays
nullable: legacy rows keep ``avg_response = null`` instead of a fake number.

Dialect safety: plain ``ADD COLUMN`` / ``DROP COLUMN`` — identical on SQLite
(dev/tests) and PostgreSQL (CI deploy proof).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd8e9f0a1b2c3'
down_revision: Union[str, Sequence[str], None] = 'c7d1e5f9a3b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add optional fulfilled_at to emergency_requests."""
    op.add_column('emergency_requests',
                  sa.Column('fulfilled_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Remove fulfilled_at."""
    op.drop_column('emergency_requests', 'fulfilled_at')
