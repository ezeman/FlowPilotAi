from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260506_0003"
down_revision = "20260506_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_email_verified", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("users", sa.Column("email_verification_token", sa.String(100), nullable=True))
    # Rename existing "admin" role to "subscriber_admin" for existing rows
    op.execute("UPDATE users SET role = 'subscriber_admin' WHERE role = 'admin'")
    # Rename "viewer" to "editor" for existing rows
    op.execute("UPDATE users SET role = 'editor' WHERE role = 'viewer'")


def downgrade() -> None:
    op.execute("UPDATE users SET role = 'admin' WHERE role = 'subscriber_admin'")
    op.execute("UPDATE users SET role = 'viewer' WHERE role = 'editor' AND role != 'editor'")
    op.drop_column("users", "email_verification_token")
    op.drop_column("users", "is_email_verified")
