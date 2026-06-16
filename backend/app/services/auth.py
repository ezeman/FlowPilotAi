from __future__ import annotations

import re
import secrets

from sqlalchemy.orm import Session

from app.core.security import get_password_hash, verify_password
from app.models.entities import Account, AccountSubscription, SubscriptionPlan, User
from app.schemas.auth import BootstrapAdminRequest, RegisterRequest
from app.services.account_scope import PLATFORM_OWNER, SUBSCRIBER_ADMIN


class EmailNotVerifiedError(Exception):
    pass


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    return cleaned.strip("-") or "default-account"


def bootstrap_admin(db: Session, payload: BootstrapAdminRequest) -> User:
    account = Account(
        name=f"{payload.full_name}'s Account",
        slug=_slugify(payload.full_name),
        is_active=True,
    )
    db.add(account)
    db.flush()

    user = User(
        account_id=account.id,
        email=payload.email.lower(),
        full_name=payload.full_name,
        hashed_password=get_password_hash(payload.password),
        role=PLATFORM_OWNER,
        is_active=True,
        is_email_verified=True,
    )
    db.add(user)
    db.flush()

    account.created_by_id = user.id
    starter_plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == "scale").first()
    if starter_plan:
        db.add(
            AccountSubscription(
                account_id=account.id,
                plan_id=starter_plan.id,
                status="active",
                auto_renew=False,
            )
        )
    db.commit()
    db.refresh(user)
    return user


def register_new_account(db: Session, payload: RegisterRequest) -> User:
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise ValueError("ไม่สามารถสร้างบัญชีได้ กรุณาตรวจสอบข้อมูลและลองใหม่อีกครั้ง")

    base_slug = _slugify(payload.account_name)
    slug = base_slug
    counter = 1
    while db.query(Account).filter(Account.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    account = Account(name=payload.account_name, slug=slug, is_active=True)
    db.add(account)
    db.flush()

    verification_token = secrets.token_urlsafe(32)
    user = User(
        account_id=account.id,
        email=payload.email.lower(),
        full_name=payload.full_name,
        hashed_password=get_password_hash(payload.password),
        role=SUBSCRIBER_ADMIN,
        is_active=True,
        is_email_verified=False,
        email_verification_token=verification_token,
    )
    db.add(user)
    db.flush()

    account.created_by_id = user.id
    db.commit()
    db.refresh(user)
    return user


def verify_email_token(db: Session, token: str) -> User:
    user = db.query(User).filter(User.email_verification_token == token).first()
    if not user:
        raise ValueError("Invalid or expired verification token")
    user.is_email_verified = True
    user.email_verification_token = None
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.query(User).filter(User.email == email.lower()).first()
    if not user or not verify_password(password, user.hashed_password):
        return None
    if not user.is_email_verified:
        raise EmailNotVerifiedError()
    return user
