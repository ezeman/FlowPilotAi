from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.entities import User
from app.schemas.settings import SettingRead, SettingUpsert
from app.services.audit import create_setting_audit
from app.services.post_workflow import upsert_setting
from app.services.account_scope import is_platform_admin, require_account
from app.models.entities import Setting

router = APIRouter()


@router.get("", response_model=list[SettingRead])
def list_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin", "editor")),
) -> list:
    return upsert_setting(db, None, current_user, list_only=True)


@router.delete("/{setting_id}")
def delete_setting(
    setting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin")),
) -> dict:
    account_id = require_account(current_user) if not is_platform_admin(current_user) else None
    query = db.query(Setting).filter(Setting.id == setting_id)
    if account_id is not None:
        query = query.filter(Setting.account_id == account_id)
    setting = query.first()
    if not setting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Setting not found")
    db.delete(setting)
    db.commit()
    return {"deleted": setting_id}


@router.put("", response_model=SettingRead)
def put_setting(
    payload: SettingUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin")),
) -> SettingRead:
    setting = upsert_setting(db, payload, current_user)
    create_setting_audit(db, current_user.id, setting.key)
    return setting
