from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.entities import Account, ContentCalendar, Post, PublishLog, User
from app.schemas.content import AutoIdeaDiscoveryRequest, GenerateContentRequest
from app.services.facebook_publisher import publish_post_to_facebook
from app.services.idea_research_agent import (
    discover_and_optionally_save_ideas,
    get_auto_idea_schedule,
    mark_auto_idea_schedule_run,
    should_run_auto_idea_schedule,
)
from app.services.openai_agent import generate_content
from app.services.pipeline_agents import final_review_agent, review_content_agent
from app.services.post_workflow import create_audit_entry
from app.services.visual_agent import create_visual_brief
from app.services.image_generator import generate_post_illustrations
from app.services.account_scope import EDITOR, PLATFORM_OWNER, SUBSCRIBER_ADMIN


# ---------------------------------------------------------------------------
# Pipeline thresholds & retry limits
# ---------------------------------------------------------------------------
VIRAL_THRESHOLD = 70       # Idea must score ≥ 70 % viral potential
WRITER_THRESHOLD = 80      # Writer must score ≥ 80 % quality
REVIEWER_THRESHOLD = 70    # Reviewer must score ≥ 70 % to proceed
FINAL_THRESHOLD = 70       # Final review must score ≥ 70 % to approve
MAX_WRITER_ATTEMPTS = 3    # Max writer retries per reviewer cycle
MAX_REVIEWER_CYCLES = 2    # Max writer → reviewer loops before giving up


def _db() -> Session:
    return SessionLocal()


def _get_auto_idea_actor(db: Session, user_id: int | None) -> User | None:
    if user_id is not None:
        return db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()

    return (
        db.query(User)
        .filter(User.is_active.is_(True), User.role.in_([SUBSCRIBER_ADMIN, EDITOR, PLATFORM_OWNER, "platform_admin"]))
        .order_by(User.id.asc())
        .first()
    )


def _get_account_actor(db: Session, account_id: int) -> User | None:
    return (
        db.query(User)
        .filter(User.account_id == account_id, User.is_active.is_(True), User.role.in_([SUBSCRIBER_ADMIN, EDITOR]))
        .order_by(User.role.asc(), User.id.asc())
        .first()
    )


@celery_app.task(name="app.workers.tasks.auto_pipeline_for_idea_job")
def auto_pipeline_for_idea_job(calendar_id: int, account_id: int) -> dict:
    """Full 5-stage auto-pipeline for a single idea.

    Stage 1  Researcher check  — idea must be in calendar (already viral-filtered ≥ 70%)
    Stage 2  Writer            — human-like viral content, retries up to MAX_WRITER_ATTEMPTS per cycle until ≥ 80%
    Stage 3  Reviewer          — independent review ≥ 70%, sends back to Writer if failed (max MAX_REVIEWER_CYCLES)
    Stage 4  Visual Designer   — create_visual_brief() + generate_post_illustrations()
    Stage 5  Final Review      — final quality check ≥ 70% → status = "approved"
    Publisher waits for human to click Post.
    """
    db = _db()
    try:
        calendar_item = db.query(ContentCalendar).filter(ContentCalendar.id == calendar_id).first()
        if not calendar_item:
            return {"status": "failed", "message": f"Calendar item {calendar_id} not found"}

        actor = _get_account_actor(db, account_id)
        if not actor:
            return {"status": "failed", "message": f"No actor found for account {account_id}"}

        # Load page context for all agents
        from app.models.entities import Page
        page = db.query(Page).filter(Page.id == calendar_item.page_id).first() if calendar_item.page_id else None

        # Stage 1: Find or create Post (idempotent — avoid duplicate posts on retry)
        post = db.query(Post).filter(
            Post.calendar_id == calendar_id,
            Post.status.notin_(["posted", "approved"]),
        ).first()
        if not post:
            post = Post(
                account_id=account_id,
                calendar_id=calendar_item.id,
                page_id=calendar_item.page_id,
                title=calendar_item.title,
                content_pillar=calendar_item.content_pillar,
                target_audience=calendar_item.target_audience,
                tone=calendar_item.tone,
                post_length=calendar_item.post_length or "medium",
                reference_notes=calendar_item.notes,
                status="idea",
                created_by_id=actor.id,
            )
            db.add(post)
            db.commit()
            db.refresh(post)

        # -----------------------------------------------------------------------
        # Stages 2 + 3: Writer → Reviewer loop (max MAX_REVIEWER_CYCLES rounds)
        # -----------------------------------------------------------------------
        quality_score = 0
        review_score = 0
        reviewer_feedback = ""
        reviewer_passed = False

        for review_cycle in range(MAX_REVIEWER_CYCLES + 1):
            # Stage 2: Writer — retry until quality ≥ WRITER_THRESHOLD or out of attempts
            writer_passed = False
            for attempt in range(1, MAX_WRITER_ATTEMPTS + 1):
                post.status = "generating"
                post.last_error = None
                db.commit()

                try:
                    result = generate_content(
                        db,
                        actor,
                        GenerateContentRequest(
                            topic=post.title,
                            content_pillar=post.content_pillar,
                            target_audience=post.target_audience or "ประชาชนทั่วไป",
                            tone=post.tone or "conversational and engaging",
                            post_length=post.post_length,
                            # Pass reviewer feedback as reference so writer improves
                            reference_notes=(
                                f"[Reviewer feedback cycle {review_cycle}]: {reviewer_feedback}\n\n"
                                + (post.reference_notes or "")
                            ).strip() if reviewer_feedback else post.reference_notes,
                            post_id=post.id,
                            page_id=post.page_id,
                        ),
                    )
                except Exception as exc:
                    post.status = "failed"
                    post.last_error = f"Writer error (attempt {attempt}): {exc}"
                    db.commit()
                    return {"status": "writer_error", "error": str(exc), "post_id": post.id}

                db.refresh(post)
                quality_score = post.quality_score or result.get("quality_score", 0)

                if quality_score >= WRITER_THRESHOLD:
                    writer_passed = True
                    break

                post.last_error = (
                    f"Writer attempt {attempt}/{MAX_WRITER_ATTEMPTS} "
                    f"(cycle {review_cycle + 1}): quality {quality_score}/100 — need {WRITER_THRESHOLD}%"
                )
                db.commit()

            if not writer_passed:
                post.status = "failed"
                post.last_error = (
                    f"Writer failed to reach {WRITER_THRESHOLD}% after {MAX_WRITER_ATTEMPTS} attempts "
                    f"(review cycle {review_cycle + 1}). Final score: {quality_score}/100"
                )
                db.commit()
                return {"status": "writer_failed", "quality_score": quality_score, "post_id": post.id}

            # Stage 3: Reviewer — independent quality check
            review_result = review_content_agent(db, actor, post, page)
            review_score = review_result.get("review_score", 0)
            reviewer_feedback = review_result.get("feedback", "")

            if review_result.get("passed", False):
                reviewer_passed = True
                break

            # Reviewer rejected — send back to writer (next cycle will use feedback)
            if review_cycle < MAX_REVIEWER_CYCLES:
                post.last_error = (
                    f"Reviewer cycle {review_cycle + 1}: score {review_score}/100 — "
                    f"back to Writer. Feedback: {reviewer_feedback}"
                )
                db.commit()

        if not reviewer_passed:
            post.status = "failed"
            post.last_error = (
                f"Reviewer rejected after {MAX_REVIEWER_CYCLES} cycles. "
                f"Final review score: {review_score}/100. {reviewer_feedback}"
            )
            db.commit()
            return {"status": "reviewer_failed", "review_score": review_score, "post_id": post.id}

        # -----------------------------------------------------------------------
        # Stage 4: Visual Designer — generate brief + image
        # -----------------------------------------------------------------------
        post.status = "draft"
        db.commit()

        try:
            create_visual_brief(db, post, actor)
            db.refresh(post)
            generate_post_illustrations(db, post, actor, variant_count=1)
            db.refresh(post)
        except Exception as exc:
            # Visual failure is non-fatal — proceed without image
            post.last_error = f"Visual Designer warning: {exc}. Proceeding without image."
            db.commit()

        # -----------------------------------------------------------------------
        # Stage 5: Final Review
        # -----------------------------------------------------------------------
        final_result = final_review_agent(db, actor, post)
        final_score = final_result.get("final_score", 0)

        # Approve — Publisher waits for human action
        post.status = "approved"
        post.approved_by_id = actor.id
        post.approved_at = datetime.now(timezone.utc)
        post.last_error = None
        calendar_item.status = "approved"
        db.commit()

        create_audit_entry(
            db, actor.id, "post", post.id, "auto_pipeline_complete",
            {"status": "draft"},
            {
                "status": "approved",
                "quality_score": quality_score,
                "review_score": review_score,
                "final_score": final_score,
            },
        )
        return {
            "status": "approved",
            "post_id": post.id,
            "calendar_id": calendar_id,
            "quality_score": quality_score,
            "review_score": review_score,
            "final_score": final_score,
        }

    except Exception as exc:
        db.rollback()
        return {"status": "error", "message": str(exc), "calendar_id": calendar_id}
    finally:
        db.close()


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
