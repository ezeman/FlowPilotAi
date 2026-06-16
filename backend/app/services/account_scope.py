from __future__ import annotations

from datetime import datetime, time, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Query, Session

from sqlalchemy import Integer, func

from app.models.entities import AIRun, Account, AccountSubscription, ContentCalendar, Page, SubscriptionPlan, User, UserPageAssignment

PLATFORM_OWNER = "platform_owner"
LEGACY_PLATFORM_ADMIN = "platform_admin"
PLATFORM_OWNER_ROLES = {PLATFORM_OWNER, LEGACY_PLATFORM_ADMIN}
SUBSCRIBER_ADMIN = "subscriber_admin"
EDITOR = "editor"
MANAGED_ROLES = {PLATFORM_OWNER, LEGACY_PLATFORM_ADMIN, SUBSCRIBER_ADMIN, EDITOR}


def is_platform_admin(user: User) -> bool:
    return user.role in PLATFORM_OWNER_ROLES


def normalize_role(role: str) -> str:
    return PLATFORM_OWNER if role == LEGACY_PLATFORM_ADMIN else role


def require_account(user: User) -> int:
    if user.account_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is not assigned to an account")
    return user.account_id


def scope_query(query: Query, model, user: User, account_field: str = "account_id") -> Query:
    return query.filter(getattr(model, account_field) == require_account(user))


def ensure_account_access(entity, user: User, account_field: str = "account_id") -> None:
    if getattr(entity, account_field) != require_account(user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")


def get_assigned_page_ids(db: Session, user: User) -> list[int]:
    if user.role != EDITOR:
        return []
    return [
        row.page_id
        for row in db.query(UserPageAssignment.page_id)
        .filter(
            UserPageAssignment.user_id == user.id,
            UserPageAssignment.account_id == require_account(user),
        )
        .all()
    ]


def require_page_access(db: Session, user: User, page_id: int | None, *, publish: bool = False) -> None:
    if is_platform_admin(user) or user.role == SUBSCRIBER_ADMIN:
        return
    if user.role != EDITOR:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    if page_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Editor access requires an assigned page")
    query = db.query(UserPageAssignment).filter(
        UserPageAssignment.user_id == user.id,
        UserPageAssignment.account_id == require_account(user),
        UserPageAssignment.page_id == page_id,
    )
    if publish:
        query = query.filter(UserPageAssignment.can_publish.is_(True))
    assignment = query.first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")


def scope_page_visible_query(query: Query, model, db: Session, user: User, page_field: str = "page_id") -> Query:
    query = query.filter(getattr(model, "account_id") == require_account(user))
    if user.role == EDITOR:
        page_ids = get_assigned_page_ids(db, user)
        if not page_ids:
            return query.filter(False)
        return query.filter(getattr(model, page_field).in_(page_ids))
    return query


def get_current_account(db: Session, user: User) -> Account | None:
    if user.account_id is None:
        return None
    return db.query(Account).filter(Account.id == user.account_id).first()


def get_active_subscription(account: Account | None) -> AccountSubscription | None:
    if not account:
        return None
    candidates = [subscription for subscription in account.subscriptions if subscription.status == "active"]
    if not candidates:
        return None
    now = datetime.now(timezone.utc)

    def _as_aware(value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    valid = [
        subscription
        for subscription in candidates
        if subscription.expires_at is None or _as_aware(subscription.expires_at) >= now
    ]
    if not valid:
        return None
    valid.sort(key=lambda item: item.created_at, reverse=True)
    return valid[0]


def get_plan_limits(account: Account | None) -> SubscriptionPlan | None:
    subscription = get_active_subscription(account)
    return subscription.plan if subscription else None


def get_usage_snapshot(db: Session, account: Account | None) -> dict:
    plan = get_plan_limits(account)
    active_subscription = get_active_subscription(account)
    if not account:
        return {
            "has_active_subscription": False,
            "subscription": None,
            "plan": None,
            "pages_used": 0,
            "users_used": 0,
            "auto_ideas_used_today": 0,
            "max_pages": 0,
            "max_users": 0,
            "max_auto_ideas_per_day": 0,
        }

    today_start = datetime.combine(datetime.now(timezone.utc).date(), time.min, tzinfo=timezone.utc)
    auto_ideas_used_today = (
        db.query(func.coalesce(func.sum(func.cast(AIRun.output_payload["created_count"].astext, Integer)), 0))
        .filter(
            AIRun.account_id == account.id,
            AIRun.run_type == "discover_ideas",
            AIRun.status == "completed",
            AIRun.created_at >= today_start,
        )
        .scalar()
        or 0
    )
    if not auto_ideas_used_today:
        auto_ideas_used_today = (
            db.query(func.count(ContentCalendar.id))
            .filter(ContentCalendar.account_id == account.id, ContentCalendar.created_at >= today_start)
            .scalar()
            or 0
        )

    return {
        "has_active_subscription": active_subscription is not None,
        "subscription": active_subscription,
        "plan": plan,
        "pages_used": db.query(func.count(Page.id)).filter(Page.account_id == account.id).scalar() or 0,
        "users_used": db.query(func.count(User.id)).filter(User.account_id == account.id, User.is_active.is_(True)).scalar() or 0,
        "auto_ideas_used_today": int(auto_ideas_used_today),
        "max_pages": plan.max_pages if plan else 0,
        "max_users": plan.max_users if plan else 0,
        "max_auto_ideas_per_day": plan.max_auto_ideas_per_day if plan else 0,
    }


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


def enforce_auto_idea_limit(account: Account, requested_count: int, db: Session | None = None) -> None:
    plan = get_plan_limits(account)
    used_today = 0
    if plan and db is not None:
        used_today = get_usage_snapshot(db, account)["auto_ideas_used_today"]
    if plan and requested_count + used_today > plan.max_auto_ideas_per_day:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Plan limit reached: maximum {plan.max_auto_ideas_per_day} auto ideas per day",
        )
