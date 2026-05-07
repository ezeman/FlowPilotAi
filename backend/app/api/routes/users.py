from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.security import get_password_hash
from app.db.session import get_db
from app.models.entities import Account, User
from app.schemas.tenant import ManagedUserCreate, ManagedUserRead, ManagedUserUpdate
from app.services.account_scope import enforce_user_limit, is_platform_admin, require_account, scope_query

router = APIRouter()


@router.get("", response_model=list[ManagedUserRead])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin", "editor")),
) -> list[User]:
    query = db.query(User).order_by(User.created_at.desc())
    if is_platform_admin(current_user):
        return scope_query(query, User, current_user).all()
    return query.filter(User.account_id == require_account(current_user)).all()


@router.post("", response_model=ManagedUserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: ManagedUserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin")),
) -> User:
    requested_account_id = payload.account_id if is_platform_admin(current_user) else require_account(current_user)
    if requested_account_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account is required")

    account = db.query(Account).filter(Account.id == requested_account_id).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    if not is_platform_admin(current_user) and current_user.role != "subscriber_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only subscriber admins can create users")

    if not is_platform_admin(current_user) and payload.role == "platform_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only platform admins can create platform admins")

    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")

    enforce_user_limit(account)

    user = User(
        account_id=account.id,
        email=payload.email.lower(),
        full_name=payload.full_name,
        hashed_password=get_password_hash(payload.password),
        role=payload.role,
        is_active=payload.is_active,
        is_email_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put("/{user_id}", response_model=ManagedUserRead)
def update_user(
    user_id: int,
    payload: ManagedUserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin")),
) -> User:
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not is_platform_admin(current_user) and target.account_id != require_account(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    if not is_platform_admin(current_user) and payload.role == "platform_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only platform admins can assign platform_admin role")

    if target.id == current_user.id and payload.is_active is False:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ไม่สามารถปิดใช้งานตัวเองได้")

    if payload.full_name is not None:
        target.full_name = payload.full_name
    if payload.role is not None:
        target.role = payload.role
    if payload.is_active is not None:
        target.is_active = payload.is_active

    db.commit()
    db.refresh(target)
    return target


@router.post("/{user_id}/verify", response_model=ManagedUserRead)
def verify_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("subscriber_admin")),
) -> User:
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    target.is_email_verified = True
    target.email_verification_token = None
    db.commit()
    db.refresh(target)
    return target
