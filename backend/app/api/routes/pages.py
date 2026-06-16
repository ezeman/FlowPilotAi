from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.encryption import encrypt_value
from app.db.session import get_db
from app.models.entities import Account, Page, Post, User
from app.schemas.content import PageCreate, PagePreferenceUpdate, PageRead, PageUpdate
from app.services.account_scope import (
    enforce_page_limit,
    ensure_account_access,
    get_assigned_page_ids,
    is_platform_admin,
    require_account,
    require_page_access,
    scope_query,
)

router = APIRouter()


@router.get("", response_model=list[PageRead])
def list_pages(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin", "editor")),
) -> list[Page]:
    if is_platform_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform owners manage subscriber accounts, not tenant pages")
    if current_user.role == "editor":
        page_ids = get_assigned_page_ids(db, current_user)
        if not page_ids:
            return []
        return db.query(Page).filter(Page.account_id == require_account(current_user), Page.id.in_(page_ids)).order_by(Page.created_at.desc()).all()
    return scope_query(db.query(Page), Page, current_user).order_by(Page.created_at.desc()).all()


@router.post("", response_model=PageRead, status_code=status.HTTP_201_CREATED)
def create_page(
    payload: PageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin")),
) -> Page:
    if is_platform_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform owners manage subscriber accounts, not tenant pages")
    account_id = require_account(current_user)
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
        default_tone=payload.default_tone,
        content_pillars=payload.content_pillars,
        is_active=payload.is_active,
        access_token_encrypted=encrypt_value(payload.access_token) if payload.access_token else None,
    )
    db.add(page)
    db.commit()
    db.refresh(page)
    return page

@router.delete("/{page_id}")
def delete_page(
    page_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin")),
) -> Response:
    if is_platform_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform owners manage subscriber accounts, not tenant pages")
    page = db.query(Page).filter(Page.id == page_id).first()
    if not page:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")
    ensure_account_access(page, current_user)
    
    # Check if page has any posts
    post_count = db.query(Post).filter(Post.page_id == page_id).count()
    if post_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete page with {post_count} post(s). Delete all posts first."
        )
    
    db.delete(page)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{page_id}/preferences", response_model=PageRead)
def update_page_preferences(
    page_id: int,
    payload: PagePreferenceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin", "editor")),
) -> Page:
    if is_platform_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform owners manage subscriber accounts, not tenant pages")
    page = db.query(Page).filter(Page.id == page_id).first()
    if not page:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")
    ensure_account_access(page, current_user)
    require_page_access(db, current_user, page.id)
    page.default_tone = payload.default_tone
    page.content_pillars = payload.content_pillars
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
    if is_platform_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform owners manage subscriber accounts, not tenant pages")
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
