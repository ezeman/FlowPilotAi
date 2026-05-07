from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260507_0005"
down_revision = "20260506_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pages", sa.Column("description", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("pages", "description")
