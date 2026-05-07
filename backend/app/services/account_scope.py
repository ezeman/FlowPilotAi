from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Query, Session

from app.models.entities import Account, AccountSubscription, SubscriptionPlan, User


def is_platform_admin(user: User) -> bool:
    return user.role == "platform_admin"


def require_account(user: User) -> int:
    effective_account_id = getattr(user, "active_account_id", None) or user.account_id
    if effective_account_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is not assigned to an account")
    return effective_account_id


def scope_query(query: Query, model, user: User, account_field: str = "account_id") -> Query:
    return query.filter(getattr(model, account_field) == require_account(user))


def ensure_account_access(entity, user: User, account_field: str = "account_id") -> None:
    if getattr(entity, account_field) != require_account(user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")


def get_current_account(db: Session, user: User) -> Account | None:
    effective_account_id = getattr(user, "active_account_id", None) or user.account_id
    if effective_account_id is None:
        return None
    return db.query(Account).filter(Account.id == effective_account_id).first()


def get_active_subscription(account: Account | None) -> AccountSubscription | None:
    if not account:
        return None
    candidates = [subscription for subscription in account.subscriptions if subscription.status == "active"]
    if not candidates:
        return None
    now = datetime.now(timezone.utc)
    valid = [
        subscription
        for subscription in candidates
        if subscription.expires_at is None or subscription.expires_at >= now
    ]
    if not valid:
        return None
    valid.sort(key=lambda item: item.created_at, reverse=True)
    return valid[0]


def get_plan_limits(account: Account | None) -> SubscriptionPlan | None:
    subscription = get_active_subscription(account)
    return subscription.plan if subscription else None


def enforce_page_limit(account: Account) -> None:
    plan = get_plan_limits(account)
    if plan and len(account.pages) >= plan.max_pages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Plan limit reached: maximum {plan.max_pages} pages",
        )


def enforce_user_limit(account: Account) -> None:
    plan = get_plan_limits(account)
    if plan and len(account.users) >= plan.max_users:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Plan limit reached: maximum {plan.max_users} users",
        )


def enforce_auto_idea_limit(account: Account, requested_count: int) -> None:
    plan = get_plan_limits(account)
    if plan and requested_count > plan.max_auto_ideas_per_day:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Plan limit reached: maximum {plan.max_auto_ideas_per_day} auto ideas per run",
        )
