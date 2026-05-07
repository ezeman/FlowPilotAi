from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.entities import PublishLog, User
from app.schemas.publish import PublishLogRead
from app.services.account_scope import scope_query

router = APIRouter()


@router.get("", response_model=list[PublishLogRead])
def list_publish_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin", "editor")),
) -> list[PublishLog]:
    return scope_query(db.query(PublishLog), PublishLog, current_user).order_by(PublishLog.attempted_at.desc()).all()
