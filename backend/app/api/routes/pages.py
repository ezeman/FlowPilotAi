from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.encryption import encrypt_value
from app.db.session import get_db
from app.models.entities import Account, Page, User
from app.schemas.content import PageCreate, PageRead, PageUpdate
from app.services.account_scope import enforce_page_limit, ensure_account_access, is_platform_admin, require_account, scope_query

router = APIRouter()


@router.get("", response_model=list[PageRead])
def list_pages(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin", "editor")),
) -> list[Page]:
    return scope_query(db.query(Page), Page, current_user).order_by(Page.created_at.desc()).all()


@router.post("", response_model=PageRead, status_code=status.HTTP_201_CREATED)
def create_page(
    payload: PageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin")),
) -> Page:
    account_id = payload.account_id if is_platform_admin(current_user) and payload.account_id else require_account(current_user)
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    enforce_page_limit(account)
    page = Page(
        account_id=account.id,
        name=payload.name,
        facebook_page_id=payload.facebook_page_id,
        page_category=payload.page_category,
        description=payload.description,
        is_active=payload.is_active,
        access_token_encrypted=encrypt_value(payload.access_token) if payload.access_token else None,
    )
    db.add(page)
    db.commit()
    db.refresh(page)
    return page


@router.put("/{page_id}", response_model=PageRead)
def update_page(
    page_id: int,
    payload: PageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin")),
) -> Page:
    page = db.query(Page).filter(Page.id == page_id).first()
    if not page:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")
    ensure_account_access(page, current_user)
    updates = payload.model_dump(exclude_unset=True)
    access_token = updates.pop("access_token", None)
    for field, value in updates.items():
        setattr(page, field, value)
    if access_token:
        page.access_token_encrypted = encrypt_value(access_token)
    db.commit()
    db.refresh(page)
    return page
