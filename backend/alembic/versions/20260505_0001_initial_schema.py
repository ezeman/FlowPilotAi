from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260505_0001"
down_revision = None
branch_labels = None
depends_on = None


DEFAULT_PILLARS = [
    "Indoor Air",
    "Outdoor Air",
    "Air Science",
    "Health Impact",
    "Environment",
    "Practical Tips",
    "Myth vs Fact",
    "Smart City",
    "Climate & Air",
    "Workplace Air Quality",
]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False, server_default="viewer"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "pages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("facebook_page_id", sa.String(length=255), nullable=False, unique=True),
        sa.Column("access_token_encrypted", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("page_category", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=120), nullable=False, unique=True),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("value_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_encrypted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "content_calendar",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("topic", sa.String(length=255), nullable=False),
        sa.Column("content_pillar", sa.String(length=120), nullable=False),
        sa.Column("target_audience", sa.String(length=255), nullable=True),
        sa.Column("tone", sa.String(length=120), nullable=True),
        sa.Column("post_length", sa.String(length=50), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="idea"),
        sa.Column("scheduled_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "posts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("calendar_id", sa.Integer(), sa.ForeignKey("content_calendar.id", ondelete="SET NULL"), nullable=True),
        sa.Column("page_id", sa.Integer(), sa.ForeignKey("pages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("hashtags", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("image_prompt", sa.Text(), nullable=True),
        sa.Column("content_pillar", sa.String(length=120), nullable=False),
        sa.Column("target_audience", sa.String(length=255), nullable=True),
        sa.Column("tone", sa.String(length=120), nullable=True),
        sa.Column("post_length", sa.String(length=50), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="idea"),
        sa.Column("reference_notes", sa.Text(), nullable=True),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("quality_score", sa.Integer(), nullable=True),
        sa.Column("fb_post_id", sa.String(length=255), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "post_assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("post_id", sa.Integer(), sa.ForeignKey("posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_type", sa.String(length=50), nullable=False),
        sa.Column("asset_url", sa.Text(), nullable=False),
        sa.Column("alt_text", sa.String(length=500), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "ai_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("post_id", sa.Integer(), sa.ForeignKey("posts.id", ondelete="CASCADE"), nullable=True),
        sa.Column("run_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("model_name", sa.String(length=120), nullable=True),
        sa.Column("prompt_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("output_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("quality_score", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        sa.sql.quoted_name("references", True),
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("post_id", sa.Integer(), sa.ForeignKey("posts.id", ondelete="CASCADE"), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=50), nullable=False, server_default="web"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "publish_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("post_id", sa.Integer(), sa.ForeignKey("posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("page_id", sa.Integer(), sa.ForeignKey("pages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("request_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("response_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("fb_post_id", sa.String(length=255), nullable=True),
        sa.Column("attempted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("entity_type", sa.String(length=120), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("before_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("after_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    pillars_json = json.dumps(DEFAULT_PILLARS, ensure_ascii=False)
    op.execute(
        sa.text(
            """
            INSERT INTO settings (key, value_json, description)
            VALUES
                ('content_pillars', CAST(:pillars AS jsonb), 'Default educational content pillars for clean-air publishing'),
                ('post_defaults', '{"language": "th", "target_word_count": "120-180", "tone": "professional and friendly"}'::jsonb, 'Default AI generation settings')
            """
        ).bindparams(pillars=pillars_json)
    )
    op.execute(
        """
        INSERT INTO settings (key, value_text, description)
        VALUES ('facebook_page_name', 'อากาศสะอาด', 'Default Facebook fanpage name')
        """
    )

    op.execute(
        """
        INSERT INTO content_calendar (title, topic, content_pillar, target_audience, tone, notes)
        VALUES
            ('ทำไมห้องนอนถึงอากาศอับกว่าที่คิด', 'ทำไมห้องนอนถึงอากาศอับกว่าที่คิด', 'Indoor Air', 'เจ้าของบ้านและคอนโด', 'professional and friendly', 'อธิบายการสะสมของ CO2 ความชื้น และการระบายอากาศในห้องนอน'),
            ('CO2 สูงในห้องประชุมส่งผลต่อสมาธิอย่างไร', 'CO2 สูงในห้องประชุมส่งผลต่อสมาธิอย่างไร', 'Workplace Air Quality', 'พนักงานออฟฟิศและผู้จัดการอาคาร', 'professional and easy to understand', 'เน้นผลต่อความง่วง สมาธิ และการจัดประชุมในพื้นที่ปิด'),
            ('VOC คืออะไร และพบได้จากของใช้ใกล้ตัวแบบไหน', 'VOC คืออะไร และพบได้จากของใช้ใกล้ตัวแบบไหน', 'Air Science', 'ครอบครัวและคนดูแลบ้าน', 'professional and friendly', 'ยกตัวอย่างสีทาผนัง น้ำหอม สเปรย์ทำความสะอาด และเฟอร์นิเจอร์ใหม่'),
            ('เชื้อราในบ้านเกี่ยวข้องกับความชื้นอย่างไร', 'เชื้อราในบ้านเกี่ยวข้องกับความชื้นอย่างไร', 'Health Impact', 'ครอบครัวที่มีเด็กและผู้สูงอายุ', 'trusted and practical', 'โยงความชื้น พื้นที่อับ และผลกระทบต่อทางเดินหายใจ'),
            ('เปิดหน้าต่างช่วยให้อากาศดีขึ้นเสมอหรือไม่', 'เปิดหน้าต่างช่วยให้อากาศดีขึ้นเสมอหรือไม่', 'Myth vs Fact', 'ผู้อยู่อาศัยในเมือง', 'neutral and practical', 'อธิบายว่าภายนอกอาจมีมลพิษหรือความชื้นสูงในบางเวลา')
        """
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("publish_logs")
    op.drop_table(sa.sql.quoted_name("references", True))
    op.drop_table("ai_runs")
    op.drop_table("post_assets")
    op.drop_table("posts")
    op.drop_table("content_calendar")
    op.drop_table("settings")
    op.drop_table("pages")
    op.drop_table("users")
