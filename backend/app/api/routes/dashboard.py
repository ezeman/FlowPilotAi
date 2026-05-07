from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.entities import ContentCalendar, Post, PublishLog, User
from app.schemas.publish import DashboardSummary, PublishLogRead
from app.services.account_scope import scope_query

router = APIRouter()


@router.get("/summary", response_model=DashboardSummary)
def summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("subscriber_admin", "editor")),
) -> DashboardSummary:
    post_counts = {
        status: count
        for status, count in scope_query(db.query(Post.status, func.count(Post.id)), Post, current_user).group_by(Post.status)
    }
    calendar_counts = {
        status: count
        for status, count in scope_query(
            db.query(ContentCalendar.status, func.count(ContentCalendar.id)),
            ContentCalendar,
            current_user,
        ).group_by(ContentCalendar.status)
    }
    latest_logs = scope_query(db.query(PublishLog), PublishLog, current_user).order_by(PublishLog.attempted_at.desc()).limit(10).all()
    upcoming_posts = scope_query(db.query(Post), Post, current_user).filter(Post.status == "scheduled").count()
    failed_publishes = scope_query(db.query(PublishLog), PublishLog, current_user).filter(PublishLog.status == "failed").count()
    return DashboardSummary(
        post_status_counts=post_counts,
        calendar_status_counts=calendar_counts,
        upcoming_posts=upcoming_posts,
        failed_publishes=failed_publishes,
        latest_publish_logs=[PublishLogRead.model_validate(item) for item in latest_logs],
    )
