from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260515_0006"
down_revision = "20260507_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("content_calendar", sa.Column("page_id", sa.Integer(), nullable=True))
    op.add_column("content_calendar", sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_content_calendar_page_id", "content_calendar", ["page_id"])
    op.create_foreign_key(
        "fk_content_calendar_page_id_pages",
        "content_calendar",
        "pages",
        ["page_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "user_page_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("page_id", sa.Integer(), sa.ForeignKey("pages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("can_create_content", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("can_edit_content", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("can_publish", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "page_id", name="uq_user_page_assignments_user_page"),
    )
    op.create_index("ix_user_page_assignments_account_id", "user_page_assignments", ["account_id"])
    op.create_index("ix_user_page_assignments_user_id", "user_page_assignments", ["user_id"])
    op.create_index("ix_user_page_assignments_page_id", "user_page_assignments", ["page_id"])


def downgrade() -> None:
    op.drop_index("ix_user_page_assignments_page_id", table_name="user_page_assignments")
    op.drop_index("ix_user_page_assignments_user_id", table_name="user_page_assignments")
    op.drop_index("ix_user_page_assignments_account_id", table_name="user_page_assignments")
    op.drop_table("user_page_assignments")
    op.drop_constraint("fk_content_calendar_page_id_pages", "content_calendar", type_="foreignkey")
    op.drop_index("ix_content_calendar_page_id", table_name="content_calendar")
    op.drop_column("content_calendar", "scheduled_for")
    op.drop_column("content_calendar", "page_id")
