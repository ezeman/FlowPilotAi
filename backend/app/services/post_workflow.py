from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.encryption import encrypt_value
from app.models.entities import AuditLog, Post, Setting, User
from app.schemas.settings import SettingUpsert
from app.services.account_scope import require_account
from app.services.audit import write_audit_log

ALLOWED_TRANSITIONS = {
    "idea": {"generating", "draft", "failed"},
    "generating": {"draft", "failed"},
    "draft": {"ready_for_review", "approved", "failed"},
    "ready_for_review": {"approved", "draft", "failed"},
    "approved": {"scheduled", "publishing", "failed"},
    "scheduled": {"publishing", "failed"},
    "publishing": {"posted", "failed"},
    "posted": set(),
    "failed": {"draft", "generating", "publishing"},
}

SENSITIVE_KEYS = {"facebook_page_access_token", "facebook_app_secret", "openai_api_key"}


def create_audit_entry(
    db: Session,
    actor_user_id: int | None,
    entity_type: str,
    entity_id: int,
    action: str,
    before: dict,
    after: dict,
) -> AuditLog:
    return write_audit_log(db, actor_user_id, entity_type, entity_id, action, before, after)


def transition_status(post: Post, next_status: str) -> None:
    allowed = ALLOWED_TRANSITIONS.get(post.status, set())
    if next_status not in allowed and next_status != post.status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid transition from {post.status} to {next_status}",
        )
    post.status = next_status


def approve_post(db: Session, post: Post, actor: User, approved: bool, notes: str | None) -> Post:
    before = {"status": post.status, "approved_by_id": post.approved_by_id}
    if approved:
        if post.status not in {"draft", "ready_for_review"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only draft or review posts can be approved")
        image_assets = [asset for asset in post.assets if asset.asset_type == "image"]
        if not image_assets:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one image asset is required before approval",
            )
        post.status = "approved"
        post.approved_by_id = actor.id
        post.approved_at = datetime.now(timezone.utc)
        post.last_error = None
        action = "approve"
    else:
        post.status = "draft"
        post.last_error = notes
        action = "reject"
    db.commit()
    db.refresh(post)
    create_audit_entry(db, actor.id, "post", post.id, action, before, {"status": post.status, "notes": notes or ""})
    return post


def schedule_post(db: Session, post: Post, actor: User, scheduled_for: datetime) -> Post:
    if post.status not in {"approved", "scheduled"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only approved posts can be scheduled")
    before = {"status": post.status, "scheduled_for": str(post.scheduled_for)}
    post.status = "scheduled"
    post.scheduled_for = scheduled_for
    if post.calendar:
        post.calendar.scheduled_for = scheduled_for
        post.calendar.scheduled_date = scheduled_for.date()
        if post.page_id and not post.calendar.page_id:
            post.calendar.page_id = post.page_id
        post.calendar.status = "scheduled"
    db.commit()
    db.refresh(post)
    create_audit_entry(
        db,
        actor.id,
        "post",
        post.id,
        "schedule",
        before,
        {"status": post.status, "scheduled_for": str(post.scheduled_for)},
    )
    return post


def upsert_setting(
    db: Session,
    payload: SettingUpsert | None,
    actor: User | None,
    list_only: bool = False,
):
    account_id = require_account(actor) if actor else None
    if list_only:
        return db.query(Setting).filter(Setting.account_id == account_id).order_by(Setting.key.asc()).all()

    setting = db.query(Setting).filter(Setting.account_id == account_id, Setting.key == payload.key).first()
    if not setting:
        setting = Setting(account_id=account_id, key=payload.key)
        db.add(setting)

    setting.description = payload.description
    setting.updated_by_id = actor.id if actor else None
    if payload.value_json is not None:
        setting.value_json = payload.value_json
        setting.value_text = None
        setting.is_encrypted = False
    else:
        value_text = payload.value_text
        should_encrypt = payload.key in SENSITIVE_KEYS or payload.key.endswith("_token")
        setting.value_text = encrypt_value(value_text) if value_text and should_encrypt else value_text
        setting.value_json = None
        setting.is_encrypted = should_encrypt and value_text is not None

    db.commit()
    db.refresh(setting)
    return setting
