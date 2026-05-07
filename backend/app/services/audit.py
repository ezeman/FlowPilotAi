from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.entities import AuditLog


def write_audit_log(
    db: Session,
    actor_user_id: int | None,
    entity_type: str,
    entity_id: int,
    action: str,
    before_json: dict,
    after_json: dict,
) -> AuditLog:
    log = AuditLog(
        actor_user_id=actor_user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        before_json=before_json,
        after_json=after_json,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def create_setting_audit(db: Session, actor_user_id: int, key: str) -> AuditLog:
    return write_audit_log(db, actor_user_id, "setting", 0, f"upsert:{key}", {}, {"key": key})
