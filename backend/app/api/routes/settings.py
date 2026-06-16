from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.encryption import encrypt_value
from app.db.session import get_db
from app.models.entities import Setting, User
from app.schemas.settings import SettingRead, SettingUpsert, SettingsDocument, SettingsPatch, UsageOverview
from app.services.audit import create_setting_audit
from app.services.post_workflow import upsert_setting
from app.services.account_scope import get_current_account, get_usage_snapshot, is_platform_admin, require_account

router = APIRouter()

ACCOUNT_SETTING_KEYS = {"default_tone", "content_pillars"}
PLATFORM_SETTING_KEYS = {"openai_api_key", "default_tone", "content_pillars"}
DEFAULT_TONE = "Professional"
DEFAULT_PILLARS = ["Education", "Promotion", "Behind the scenes"]
MASKED_SECRET = "********"


def _get_setting(db: Session, account_id: int | None, key: str) -> Setting | None:
    return db.query(Setting).filter(Setting.account_id == account_id, Setting.key == key).order_by(Setting.id.desc()).first()


def _setting_value(setting: Setting | None, default):
    if not setting:
        return default
    if setting.value_json is not None:
        return setting.value_json
    if setting.is_encrypted:
        return MASKED_SECRET
    return setting.value_text if setting.value_text not in (None, "") else default


def _upsert_scoped_setting(
    db: Session,
    *,
    account_id: int | None,
    key: str,
    value_text: str | None = None,
    value_json=None,
    actor: User,
    encrypted: bool = False,
) -> Setting:
    setting = _get_setting(db, account_id, key)
    if not setting:
        setting = Setting(account_id=account_id, key=key)
        db.add(setting)
    setting.updated_by_id = actor.id
    setting.description = "Managed from Settings"
    if value_json is not None:
        setting.value_json = value_json
        setting.value_text = None
        setting.is_encrypted = False
    else:
        setting.value_json = None
        setting.value_text = encrypt_value(value_text) if value_text and encrypted else value_text
        setting.is_encrypted = encrypted and value_text is not None
    db.commit()
    db.refresh(setting)
    create_setting_audit(db, actor.id, setting.key)
    return setting


def _build_settings_document(db: Session, current_user: User) -> SettingsDocument:
    current_account = get_current_account(db, current_user)
    account_id = current_account.id if current_account else None
    if account_id is None and not is_platform_admin(current_user):
        require_account(current_user)
    account_settings = {
        "default_tone": _setting_value(_get_setting(db, account_id, "default_tone"), DEFAULT_TONE),
        "content_pillars": _setting_value(_get_setting(db, account_id, "content_pillars"), DEFAULT_PILLARS),
    }
    platform_settings = None
    if is_platform_admin(current_user):
        api_key = _get_setting(db, None, "openai_api_key")
        platform_settings = {
            "openai_api_key": MASKED_SECRET if api_key and api_key.value_text else "",
            "has_openai_api_key": bool(api_key and api_key.value_text),
            "default_tone": _setting_value(_get_setting(db, None, "default_tone"), DEFAULT_TONE),
            "content_pillars": _setting_value(_get_setting(db, None, "content_pillars"), DEFAULT_PILLARS),
        }
    return SettingsDocument(account=account_settings, platform=platform_settings)


@router.get("", response_model=SettingsDocument)
def list_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin", "editor", check_subscription=False)),
) -> SettingsDocument:
    return _build_settings_document(db, current_user)


@router.get("/usage", response_model=UsageOverview)
def get_usage(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin", "editor", check_subscription=False)),
) -> dict:
    return get_usage_snapshot(db, get_current_account(db, current_user))


@router.patch("", response_model=SettingsDocument)
def patch_settings(
    payload: SettingsPatch,
    scope: str = Query(default="account", pattern="^(account|platform)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin", check_subscription=False)),
) -> SettingsDocument:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No settings to update")

    if scope == "platform":
        if not is_platform_admin(current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only platform admins can manage platform settings")
        allowed = PLATFORM_SETTING_KEYS
        account_id = None
    else:
        allowed = ACCOUNT_SETTING_KEYS
        account_id = require_account(current_user)

    forbidden = set(updates) - allowed
    if forbidden:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Cannot update setting: {', '.join(sorted(forbidden))}")

    if "default_tone" in updates:
        _upsert_scoped_setting(db, account_id=account_id, key="default_tone", value_text=updates["default_tone"], actor=current_user)
    if "content_pillars" in updates:
        _upsert_scoped_setting(db, account_id=account_id, key="content_pillars", value_json=updates["content_pillars"], actor=current_user)
    if "openai_api_key" in updates and updates["openai_api_key"]:
        _upsert_scoped_setting(
            db,
            account_id=None,
            key="openai_api_key",
            value_text=updates["openai_api_key"],
            actor=current_user,
            encrypted=True,
        )

    return _build_settings_document(db, current_user)


@router.delete("/{setting_id}")
def delete_setting(
    setting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin", check_subscription=False)),
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
    current_user: User = Depends(require_roles("subscriber_admin", check_subscription=False)),
) -> SettingRead:
    if not is_platform_admin(current_user) and payload.key not in ACCOUNT_SETTING_KEYS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot update this setting")
    if is_platform_admin(current_user) and payload.key == "openai_api_key":
        setting = _upsert_scoped_setting(
            db,
            account_id=None,
            key=payload.key,
            value_text=payload.value_text,
            actor=current_user,
            encrypted=True,
        )
        setattr(setting, "value_text", MASKED_SECRET)
        return setting
    setting = upsert_setting(db, payload, current_user)
    create_setting_audit(db, current_user.id, setting.key)
    return setting
