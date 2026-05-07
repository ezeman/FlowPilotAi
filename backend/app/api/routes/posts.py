from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.entities import ContentCalendar, Page, Post, User
from app.schemas.content import (
    GenerateContentRequest,
    GenerateContentResponse,
    ImageGenerationRequest,
    PostCreate,
    PostRead,
    PostUpdate,
    ReviewDecisionRequest,
    SchedulePostRequest,
)
from app.services.account_scope import ensure_account_access, require_account, scope_query
from app.services.image_generator import generate_post_illustrations
from app.services.openai_agent import generate_content
from app.services.post_workflow import approve_post, create_audit_entry, schedule_post
from app.services.visual_agent import create_visual_brief
from app.workers.tasks import generate_content_job, publish_facebook_post_job, review_content_job

router = APIRouter()


def _validate_related_entities(db: Session, current_user: User, page_id: int | None, calendar_id: int | None) -> None:
    if page_id is not None:
        page = db.query(Page).filter(Page.id == page_id).first()
        if not page:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")
        ensure_account_access(page, current_user)
    if calendar_id is not None:
        calendar_item = db.query(ContentCalendar).filter(ContentCalendar.id == calendar_id).first()
        if not calendar_item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Calendar item not found")
        ensure_account_access(calendar_item, current_user)


@router.get("", response_model=list[PostRead])
def list_posts(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin", "editor")),
) -> list[Post]:
    return scope_query(db.query(Post), Post, current_user).order_by(Post.updated_at.desc()).all()


@router.post("", response_model=PostRead, status_code=status.HTTP_201_CREATED)
def create_post(
    payload: PostCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin", "editor")),
) -> Post:
    _validate_related_entities(db, current_user, payload.page_id, payload.calendar_id)
    post = Post(
        **payload.model_dump(exclude={"account_id"}),
        account_id=require_account(current_user),
        created_by_id=current_user.id,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    create_audit_entry(db, current_user.id, "post", post.id, "create", {}, {"title": post.title, "status": post.status})
    return post


@router.get("/{post_id}", response_model=PostRead)
def get_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin", "editor")),
) -> Post:
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    ensure_account_access(post, current_user)
    return post


@router.put("/{post_id}", response_model=PostRead)
def update_post(
    post_id: int,
    payload: PostUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin", "editor")),
) -> Post:
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    ensure_account_access(post, current_user)
    _validate_related_entities(
        db,
        current_user,
        payload.page_id if "page_id" in payload.model_dump(exclude_unset=True) else post.page_id,
        payload.calendar_id if "calendar_id" in payload.model_dump(exclude_unset=True) else post.calendar_id,
    )
    before = {"title": post.title, "caption": post.caption, "status": post.status, "scheduled_for": str(post.scheduled_for)}
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "account_id":
            continue
        setattr(post, field, value)
    db.commit()
    db.refresh(post)
    create_audit_entry(
        db,
        current_user.id,
        "post",
        post.id,
        "update",
        before,
        {"title": post.title, "caption": post.caption, "status": post.status, "scheduled_for": str(post.scheduled_for)},
    )
    return post


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin", "editor")),
) -> Response:
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    ensure_account_access(post, current_user)
    if post.status not in {"idea", "draft", "failed"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only idea, draft, or failed posts can be deleted",
        )
    create_audit_entry(db, current_user.id, "post", post.id, "delete", {"title": post.title, "status": post.status}, {})
    db.delete(post)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/ai/generate", response_model=GenerateContentResponse)
def generate_content_preview(
    payload: GenerateContentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin", "editor")),
) -> GenerateContentResponse:
    if payload.post_id:
        linked_post = db.query(Post).filter(Post.id == payload.post_id).first()
        if not linked_post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
        ensure_account_access(linked_post, current_user)
    result = generate_content(db, current_user, payload)
    return GenerateContentResponse(**result)


@router.post("/{post_id}/generate", status_code=status.HTTP_202_ACCEPTED)
def enqueue_generation(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin", "editor")),
) -> dict[str, str]:
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    ensure_account_access(post, current_user)
    task = generate_content_job.delay(post_id, current_user.id)
    return {"task_id": task.id, "message": "Content generation queued"}


@router.post("/{post_id}/review", status_code=status.HTTP_202_ACCEPTED)
def enqueue_review(
    post_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("subscriber_admin", "editor")),
) -> dict[str, str]:
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    ensure_account_access(post, _)
    task = review_content_job.delay(post_id)
    return {"task_id": task.id, "message": "Review queued"}


@router.post("/{post_id}/approve", response_model=PostRead)
def review_post(
    post_id: int,
    payload: ReviewDecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin", "editor")),
) -> Post:
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    ensure_account_access(post, current_user)
    return approve_post(db, post, current_user, payload.approved, payload.notes)


@router.post("/{post_id}/schedule", response_model=PostRead)
def schedule_existing_post(
    post_id: int,
    payload: SchedulePostRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin", "editor")),
) -> Post:
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    ensure_account_access(post, current_user)
    return schedule_post(db, post, current_user, payload.scheduled_for)


@router.post("/{post_id}/publish", status_code=status.HTTP_202_ACCEPTED)
def publish_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin", "editor")),
) -> dict[str, str]:
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    ensure_account_access(post, current_user)
    if post.status != "approved" and post.status != "scheduled":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only approved or scheduled posts can be published")
    task = publish_facebook_post_job.delay(post_id)
    return {"task_id": task.id, "message": "Publish job queued"}


@router.post("/{post_id}/generate-image", response_model=PostRead)
def generate_post_image(
    post_id: int,
    payload: ImageGenerationRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin", "editor")),
) -> Post:
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    ensure_account_access(post, current_user)
    before_asset_count = len(post.assets)
    request = payload or ImageGenerationRequest()
    updated_post = generate_post_illustrations(db, post, current_user, request.variant_count)
    create_audit_entry(
        db,
        current_user.id,
        "post",
        post.id,
        "generate_image",
        {"asset_count": before_asset_count},
        {"asset_count": len(updated_post.assets), "variant_count": request.variant_count},
    )
    return updated_post


@router.post("/{post_id}/visual-brief", response_model=PostRead)
def generate_visual_brief(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin", "editor")),
) -> Post:
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    ensure_account_access(post, current_user)
    before_prompt = post.image_prompt
    updated_post = create_visual_brief(db, post, current_user)
    create_audit_entry(
        db,
        current_user.id,
        "post",
        post.id,
        "generate_visual_brief",
        {"image_prompt": before_prompt},
        {"image_prompt": updated_post.image_prompt},
    )
    return updated_post
