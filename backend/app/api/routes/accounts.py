from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.entities import Account, AccountSubscription, SubscriptionPlan, User
from app.schemas.tenant import AccountCreate, AccountRead, AccountSubscriptionRead, AccountSubscriptionUpdate, SubscriptionPlanRead
from app.services.account_scope import get_active_subscription, get_current_account, is_platform_admin, require_account

router = APIRouter()


def _hydrate_account(account: Account) -> AccountRead:
    return AccountRead.model_validate(
        {
            "id": account.id,
            "name": account.name,
            "slug": account.slug,
            "is_active": account.is_active,
            "created_by_id": account.created_by_id,
            "created_at": account.created_at,
            "updated_at": account.updated_at,
            "active_subscription": get_active_subscription(account),
            "usage": {
                "pages_used": len(account.pages),
                "users_used": len(account.users),
                "posts_used": len(account.posts),
                "ideas_used": len(account.content_calendar_items),
            },
        }
    )


@router.get("", response_model=list[AccountRead])
def list_accounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin", "editor")),
) -> list[Account]:
    if is_platform_admin(current_user):
        accounts = db.query(Account).order_by(Account.created_at.desc()).all()
        return [_hydrate_account(account) for account in accounts]

    account = get_current_account(db, current_user)
    return [_hydrate_account(account)] if account else []


@router.get("/plans", response_model=list[SubscriptionPlanRead])
def list_plans(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("subscriber_admin", "editor", check_subscription=False)),
) -> list[SubscriptionPlan]:
    return db.query(SubscriptionPlan).filter(SubscriptionPlan.is_active.is_(True)).order_by(SubscriptionPlan.price_monthly.asc()).all()


@router.get("/me/subscription", response_model=AccountSubscriptionRead | None)
def get_my_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin", "editor", check_subscription=False)),
) -> AccountSubscription | None:
    account = get_current_account(db, current_user)
    return get_active_subscription(account)


@router.post("", response_model=AccountRead, status_code=status.HTTP_201_CREATED)
def create_account(
    payload: AccountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Account:
    if not is_platform_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only platform admins can create accounts")

    existing = db.query(Account).filter((Account.name == payload.name) | (Account.slug == payload.slug)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Account name or slug already exists")

    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == payload.plan_code).first()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    account = Account(name=payload.name, slug=payload.slug, is_active=True, created_by_id=current_user.id)
    db.add(account)
    db.flush()
    db.add(AccountSubscription(account_id=account.id, plan_id=plan.id, status="active", auto_renew=False))
    db.commit()
    db.refresh(account)
    return _hydrate_account(account)


@router.put("/{account_id}/subscription", response_model=AccountSubscriptionRead)
def update_account_subscription(
    account_id: int,
    payload: AccountSubscriptionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AccountSubscription:
    if not is_platform_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only platform admins can manage subscriptions")

    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == payload.plan_code).first()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    subscription = get_active_subscription(account)
    if not subscription:
        subscription = AccountSubscription(account_id=account.id, plan_id=plan.id)
        db.add(subscription)

    subscription.plan_id = plan.id
    subscription.status = payload.status
    subscription.expires_at = payload.expires_at
    subscription.auto_renew = payload.auto_renew
    db.commit()
    db.refresh(subscription)
    return subscription
