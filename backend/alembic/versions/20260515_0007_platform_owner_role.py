from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260515_0007"
down_revision = "20260515_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE users SET role = 'platform_owner' WHERE role = 'platform_admin'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE users SET role = 'platform_admin' WHERE role = 'platform_owner'"))
