from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260515_0008"
down_revision = "20260515_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pages", sa.Column("default_tone", sa.String(length=80), nullable=True))
    op.add_column("pages", sa.Column("content_pillars", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("pages", "content_pillars")
    op.drop_column("pages", "default_tone")
