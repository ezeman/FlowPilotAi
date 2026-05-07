from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260506_0002"
down_revision = "20260505_0001"
branch_labels = None
depends_on = None


PLAN_SEED = [
    {
        "code": "starter",
        "name": "Starter",
        "description": "Small team plan for a single brand",
        "price_monthly": 2900,
        "max_pages": 3,
        "max_users": 3,
        "max_auto_ideas_per_day": 5,
    },
    {
        "code": "growth",
        "name": "Growth",
        "description": "Growing team with more pages and editors",
        "price_monthly": 7900,
        "max_pages": 10,
        "max_users": 10,
        "max_auto_ideas_per_day": 10,
    },
    {
        "code": "scale",
        "name": "Scale",
        "description": "Agency or multi-brand plan",
        "price_monthly": 19900,
        "max_pages": 50,
        "max_users": 50,
        "max_auto_ideas_per_day": 10,
    },
]


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False, unique=True),
        sa.Column("slug", sa.String(length=120), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "subscription_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=60), nullable=False, unique=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("price_monthly", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_pages", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_users", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_auto_ideas_per_day", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "account_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("subscription_plans.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="active"),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("auto_renew", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.add_column("users", sa.Column("account_id", sa.Integer(), nullable=True))
    op.add_column("pages", sa.Column("account_id", sa.Integer(), nullable=True))
    op.add_column("content_calendar", sa.Column("account_id", sa.Integer(), nullable=True))
    op.add_column("posts", sa.Column("account_id", sa.Integer(), nullable=True))
    op.add_column("ai_runs", sa.Column("account_id", sa.Integer(), nullable=True))
    op.add_column("publish_logs", sa.Column("account_id", sa.Integer(), nullable=True))
    op.add_column("settings", sa.Column("account_id", sa.Integer(), nullable=True))

    op.create_foreign_key("fk_users_account_id_accounts", "users", "accounts", ["account_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_pages_account_id_accounts", "pages", "accounts", ["account_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key("fk_content_calendar_account_id_accounts", "content_calendar", "accounts", ["account_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key("fk_posts_account_id_accounts", "posts", "accounts", ["account_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key("fk_ai_runs_account_id_accounts", "ai_runs", "accounts", ["account_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_publish_logs_account_id_accounts", "publish_logs", "accounts", ["account_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_settings_account_id_accounts", "settings", "accounts", ["account_id"], ["id"], ondelete="CASCADE")

    op.create_index("ix_users_account_id", "users", ["account_id"])
    op.create_index("ix_pages_account_id", "pages", ["account_id"])
    op.create_index("ix_content_calendar_account_id", "content_calendar", ["account_id"])
    op.create_index("ix_posts_account_id", "posts", ["account_id"])
    op.create_index("ix_ai_runs_account_id", "ai_runs", ["account_id"])
    op.create_index("ix_publish_logs_account_id", "publish_logs", ["account_id"])
    op.create_index("ix_settings_account_id", "settings", ["account_id"])

    connection = op.get_bind()

    for plan in PLAN_SEED:
        connection.execute(
            sa.text(
                """
                INSERT INTO subscription_plans
                    (code, name, description, price_monthly, max_pages, max_users, max_auto_ideas_per_day)
                VALUES
                    (:code, :name, :description, :price_monthly, :max_pages, :max_users, :max_auto_ideas_per_day)
                """
            ),
            plan,
        )

    first_user = connection.execute(sa.text("SELECT id, full_name FROM users ORDER BY id ASC LIMIT 1")).mappings().first()
    if first_user:
        account_name = f"{first_user['full_name']} Account"
        account_slug = "default-account"
        account_id = connection.execute(
            sa.text(
                """
                INSERT INTO accounts (name, slug, is_active, created_by_id)
                VALUES (:name, :slug, true, :created_by_id)
                RETURNING id
                """
            ),
            {"name": account_name, "slug": account_slug, "created_by_id": first_user["id"]},
        ).scalar_one()

        connection.execute(sa.text("UPDATE users SET account_id = :account_id"), {"account_id": account_id})
        connection.execute(
            sa.text(
                """
                UPDATE users
                SET role = 'platform_admin'
                WHERE id = (SELECT id FROM users ORDER BY id ASC LIMIT 1)
                """
            )
        )
        connection.execute(sa.text("UPDATE pages SET account_id = :account_id"), {"account_id": account_id})
        connection.execute(sa.text("UPDATE content_calendar SET account_id = :account_id"), {"account_id": account_id})
        connection.execute(sa.text("UPDATE posts SET account_id = :account_id"), {"account_id": account_id})
        connection.execute(sa.text("UPDATE ai_runs SET account_id = :account_id"), {"account_id": account_id})
        connection.execute(sa.text("UPDATE publish_logs SET account_id = :account_id"), {"account_id": account_id})
        connection.execute(sa.text("UPDATE settings SET account_id = :account_id"), {"account_id": account_id})

        scale_plan_id = connection.execute(
            sa.text("SELECT id FROM subscription_plans WHERE code = 'scale' LIMIT 1")
        ).scalar_one()
        connection.execute(
            sa.text(
                """
                INSERT INTO account_subscriptions (account_id, plan_id, status, auto_renew)
                VALUES (:account_id, :plan_id, 'active', false)
                """
            ),
            {"account_id": account_id, "plan_id": scale_plan_id},
        )

    connection.execute(sa.text("DELETE FROM content_calendar WHERE account_id IS NULL"))
    connection.execute(sa.text("DELETE FROM posts WHERE account_id IS NULL"))
    connection.execute(sa.text("DELETE FROM pages WHERE account_id IS NULL"))

    op.alter_column("pages", "account_id", nullable=False)
    op.alter_column("content_calendar", "account_id", nullable=False)
    op.alter_column("posts", "account_id", nullable=False)

    connection.execute(sa.text("DROP INDEX IF EXISTS ix_settings_key"))
    connection.execute(sa.text("ALTER TABLE settings DROP CONSTRAINT IF EXISTS settings_key_key"))
    op.create_index("ix_settings_key", "settings", ["key"])
    op.create_index("uq_settings_account_key", "settings", ["account_id", "key"], unique=True)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_settings_account_key")
    op.execute("DROP INDEX IF EXISTS ix_settings_key")
    op.create_index("ix_settings_key", "settings", ["key"], unique=False)
    op.create_unique_constraint("settings_key_key", "settings", ["key"])

    op.drop_index("ix_settings_account_id", table_name="settings")
    op.drop_index("ix_publish_logs_account_id", table_name="publish_logs")
    op.drop_index("ix_ai_runs_account_id", table_name="ai_runs")
    op.drop_index("ix_posts_account_id", table_name="posts")
    op.drop_index("ix_content_calendar_account_id", table_name="content_calendar")
    op.drop_index("ix_pages_account_id", table_name="pages")
    op.drop_index("ix_users_account_id", table_name="users")

    op.drop_constraint("fk_settings_account_id_accounts", "settings", type_="foreignkey")
    op.drop_constraint("fk_publish_logs_account_id_accounts", "publish_logs", type_="foreignkey")
    op.drop_constraint("fk_ai_runs_account_id_accounts", "ai_runs", type_="foreignkey")
    op.drop_constraint("fk_posts_account_id_accounts", "posts", type_="foreignkey")
    op.drop_constraint("fk_content_calendar_account_id_accounts", "content_calendar", type_="foreignkey")
    op.drop_constraint("fk_pages_account_id_accounts", "pages", type_="foreignkey")
    op.drop_constraint("fk_users_account_id_accounts", "users", type_="foreignkey")

    op.drop_column("settings", "account_id")
    op.drop_column("publish_logs", "account_id")
    op.drop_column("ai_runs", "account_id")
    op.drop_column("posts", "account_id")
    op.drop_column("content_calendar", "account_id")
    op.drop_column("pages", "account_id")
    op.drop_column("users", "account_id")

    op.drop_table("account_subscriptions")
    op.drop_table("subscription_plans")
    op.drop_table("accounts")
