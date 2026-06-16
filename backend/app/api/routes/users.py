from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.security import get_password_hash
from app.db.session import get_db
from app.models.entities import Account, Page, User, UserPageAssignment
from app.schemas.tenant import ManagedUserCreate, ManagedUserRead, ManagedUserUpdate
from app.services.account_scope import (
    EDITOR,
    MANAGED_ROLES,
    SUBSCRIBER_ADMIN,
    enforce_user_limit,
    is_platform_admin,
    normalize_role,
    require_account,
)

router = APIRouter()


def _attach_assigned_page_ids(users: list[User]) -> list[User]:
    for user in users:
        setattr(user, "assigned_page_ids", [assignment.page_id for assignment in user.page_assignments])
    return users


def _validate_page_assignments(db: Session, account_id: int, page_ids: list[int]) -> list[int]:
    unique_ids = sorted(set(page_ids))
    if not unique_ids:
        return []
    count = db.query(Page).filter(Page.account_id == account_id, Page.id.in_(unique_ids)).count()
    if count != len(unique_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more assigned pages are not in this account")
    return unique_ids


def _sync_page_assignments(db: Session, user: User, page_ids: list[int]) -> None:
    if user.role != EDITOR:
        db.query(UserPageAssignment).filter(UserPageAssignment.user_id == user.id).delete()
        return
    next_ids = _validate_page_assignments(db, user.account_id, page_ids)
    existing = {assignment.page_id: assignment for assignment in user.page_assignments}
    for page_id, assignment in list(existing.items()):
        if page_id not in next_ids:
            db.delete(assignment)
    for page_id in next_ids:
        if page_id not in existing:
            db.add(
                UserPageAssignment(
                    account_id=user.account_id,
                    user_id=user.id,
                    page_id=page_id,
                    can_create_content=True,
                    can_edit_content=True,
                    can_publish=False,
                )
            )


@router.get("", response_model=list[ManagedUserRead])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin")),
) -> list[User]:
    if is_platform_admin(current_user):
        query = (
            db.query(User)
            .filter(User.account_id.is_not(None), User.role.in_([SUBSCRIBER_ADMIN, EDITOR]))
            .order_by(User.account_id.asc(), User.role.asc(), User.created_at.desc())
        )
        return _attach_assigned_page_ids(query.all())
    query = db.query(User).order_by(User.created_at.desc())
    return _attach_assigned_page_ids(query.filter(User.account_id == require_account(current_user)).all())


@router.post("", response_model=ManagedUserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: ManagedUserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin")),
) -> User:
    if is_platform_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform owners manage subscriber accounts, not tenant team users")
    requested_account_id = require_account(current_user)
    if requested_account_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account is required")

    account = db.query(Account).filter(Account.id == requested_account_id).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    if current_user.role != SUBSCRIBER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only subscriber admins can create users")

    role = normalize_role(payload.role)
    if role not in MANAGED_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported role")
    if role != EDITOR:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Subscriber admins can create editor users only")

    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")

    enforce_user_limit(account)

    user = User(
        account_id=account.id,
        email=payload.email.lower(),
        full_name=payload.full_name,
        hashed_password=get_password_hash(payload.password),
        role=role,
        is_active=payload.is_active,
        is_email_verified=True,
    )
    db.add(user)
    db.flush()
    _sync_page_assignments(db, user, payload.assigned_page_ids)
    db.commit()
    db.refresh(user)
    setattr(user, "assigned_page_ids", [assignment.page_id for assignment in user.page_assignments])
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

    if is_platform_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform owners manage subscriber accounts, not tenant team users")
    if target.account_id != require_account(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    if target.id == current_user.id and payload.is_active is False:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ไม่สามารถปิดใช้งานตัวเองได้")

    next_role = normalize_role(payload.role) if payload.role is not None else target.role
    if next_role not in MANAGED_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported role")
    if target.role != EDITOR or next_role != EDITOR:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Subscriber admins can manage editor users only")

    if payload.full_name is not None:
        target.full_name = payload.full_name
    if payload.role is not None:
        target.role = next_role
    if payload.is_active is not None:
        target.is_active = payload.is_active
    if payload.assigned_page_ids is not None:
        _sync_page_assignments(db, target, payload.assigned_page_ids)

    db.commit()
    db.refresh(target)
    setattr(target, "assigned_page_ids", [assignment.page_id for assignment in target.page_assignments])
    return target


@router.post("/{user_id}/verify", response_model=ManagedUserRead)
def verify_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin")),
) -> User:
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if is_platform_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform owners manage subscriber accounts, not tenant team users")
    if target.account_id != require_account(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    if target.role != EDITOR:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Subscriber admins can verify editor users only")
    target.is_email_verified = True
    target.email_verification_token = None
    db.commit()
    db.refresh(target)
    setattr(target, "assigned_page_ids", [assignment.page_id for assignment in target.page_assignments])
    return target
