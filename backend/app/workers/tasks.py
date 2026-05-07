from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.entities import Account, Post, PublishLog, User
from app.schemas.content import AutoIdeaDiscoveryRequest, GenerateContentRequest
from app.services.facebook_publisher import publish_post_to_facebook
from app.services.idea_research_agent import (
    discover_and_optionally_save_ideas,
    get_auto_idea_schedule,
    mark_auto_idea_schedule_run,
    should_run_auto_idea_schedule,
)
from app.services.openai_agent import generate_content
from app.services.post_workflow import create_audit_entry


def _db() -> Session:
    return SessionLocal()


def _get_auto_idea_actor(db: Session, user_id: int | None) -> User | None:
    if user_id is not None:
        return db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()

    return (
        db.query(User)
        .filter(User.is_active.is_(True), User.role.in_(["admin", "editor"]))
        .order_by(User.id.asc())
        .first()
    )


def _get_account_actor(db: Session, account_id: int) -> User | None:
    return (
        db.query(User)
        .filter(User.account_id == account_id, User.is_active.is_(True), User.role.in_(["admin", "editor"]))
        .order_by(User.role.asc(), User.id.asc())
        .first()
    )


@celery_app.task(name="app.workers.tasks.generate_content_job")
def generate_content_job(post_id: int, user_id: int) -> dict:
    db = _db()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        user = db.query(User).filter(User.id == user_id).first()
        if not post or not user:
            return {"status": "failed", "message": "Post or user not found"}
        post.status = "generating"
        db.commit()
        result = generate_content(
            db,
            user,
            GenerateContentRequest(
                topic=post.title,
                content_pillar=post.content_pillar,
                target_audience=post.target_audience or "ประชาชนทั่วไป",
                tone=post.tone or "professional and friendly",
                post_length=post.post_length,
                reference_notes=post.reference_notes,
                post_id=post.id,
            ),
        )
        create_audit_entry(db, user.id, "post", post.id, "generate_content", {"status": "generating"}, {"status": "draft"})
        return {"status": "completed", "result": result}
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.review_content_job")
def review_content_job(post_id: int) -> dict:
    db = _db()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            return {"status": "failed", "message": "Post not found"}
        if post.caption and 120 <= len(post.caption.split()) <= 220:
            post.status = "ready_for_review"
            post.last_error = None
        else:
            post.status = "draft"
            post.last_error = "AI draft should be reviewed for length and clarity"
        db.commit()
        return {"status": "completed", "post_status": post.status}
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.generate_image_prompt_job")
def generate_image_prompt_job(post_id: int) -> dict:
    db = _db()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            return {"status": "failed", "message": "Post not found"}
        if not post.image_prompt:
            post.image_prompt = f"Thai educational cover illustration for {post.title}, clean air, informative layout"
            db.commit()
        return {"status": "completed", "image_prompt": post.image_prompt}
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.publish_facebook_post_job")
def publish_facebook_post_job(post_id: int) -> dict:
    db = _db()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            return {"status": "failed", "message": "Post not found"}
        post.status = "publishing"
        db.commit()
        log = publish_post_to_facebook(db, post)
        return {"status": log.status, "fb_post_id": log.fb_post_id, "error_message": log.error_message}
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.retry_failed_publish_job")
def retry_failed_publish_job() -> dict:
    db = _db()
    retried = 0
    try:
        failed_posts = db.query(Post).filter(Post.status == "failed", Post.page_id.isnot(None)).limit(10).all()
        for post in failed_posts:
            if post.approved_by_id:
                publish_post_to_facebook(db, post)
                retried += 1
        return {"status": "completed", "retried": retried}
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.sync_facebook_metrics_job")
def sync_facebook_metrics_job() -> dict:
    db = _db()
    try:
        recent_logs = db.query(PublishLog).filter(PublishLog.status == "success").limit(20).all()
        return {"status": "completed", "synced_logs": len(recent_logs), "note": "Metrics sync scaffold ready for extension"}
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.auto_generate_daily_ideas_job")
def auto_generate_daily_ideas_job(user_id: int | None = None, force: bool = False) -> dict:
    db = _db()
    try:
        now = datetime.now()
        if user_id is not None:
            actor = _get_auto_idea_actor(db, user_id)
            if not actor or actor.account_id is None:
                return {"status": "failed", "message": "No eligible admin or editor user found"}
            schedule = get_auto_idea_schedule(db, actor.account_id)
            config = schedule.config
            if force and not config.enabled:
                config = config.model_copy(update={"enabled": True})
            elif not force:
                should_run, config = should_run_auto_idea_schedule(db, actor.account_id, now)
                if not should_run:
                    return {"status": "skipped", "message": "Schedule is not due", "account_id": actor.account_id}

            items, sources_checked = discover_and_optionally_save_ideas(
                db,
                actor,
                AutoIdeaDiscoveryRequest(count=config.count, save_to_calendar=True),
            )
            local_date = now.strftime("%Y-%m-%d")
            mark_auto_idea_schedule_run(db, actor.account_id, local_date)
            return {
                "status": "completed",
                "account_id": actor.account_id,
                "created_count": len(items),
                "sources_checked": len(sources_checked),
                "run_date": local_date,
                "time_local": config.time_local,
            }

        processed_accounts = 0
        total_created = 0
        local_date = now.strftime("%Y-%m-%d")
        for account in db.query(Account).filter(Account.is_active.is_(True)).all():
            actor = _get_account_actor(db, account.id)
            if not actor:
                continue
            should_run, config = should_run_auto_idea_schedule(db, account.id, now)
            if not should_run:
                continue
            items, _ = discover_and_optionally_save_ideas(
                db,
                actor,
                AutoIdeaDiscoveryRequest(count=config.count, save_to_calendar=True),
            )
            mark_auto_idea_schedule_run(db, account.id, local_date)
            processed_accounts += 1
            total_created += len(items)

        return {"status": "completed", "accounts_processed": processed_accounts, "created_count": total_created, "run_date": local_date}
    finally:
        db.close()
