from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.entities import AccountSubscription, SubscriptionPlan, User
from app.schemas.tenant import AccountSubscriptionRead, SubscriptionPlanRead
from app.services.account_scope import get_active_subscription, get_current_account

router = APIRouter()


@router.get("/current", response_model=AccountSubscriptionRead | None)
def get_current_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin", "editor", check_subscription=False)),
) -> AccountSubscription | None:
    return get_active_subscription(get_current_account(db, current_user))


@router.get("/plans", response_model=list[SubscriptionPlanRead])
def list_subscription_plans(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("subscriber_admin", "editor", check_subscription=False)),
) -> list[SubscriptionPlan]:
    return db.query(SubscriptionPlan).filter(SubscriptionPlan.is_active.is_(True)).order_by(SubscriptionPlan.price_monthly.asc()).all()
