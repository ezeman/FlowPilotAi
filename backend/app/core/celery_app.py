from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "ezecraft_ai",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Bangkok",
    beat_schedule={
        "auto-generate-daily-ideas-check": {
            "task": "app.workers.tasks.auto_generate_daily_ideas_job",
            "schedule": 300.0,
        },
        "retry-failed-publishes": {
            "task": "app.workers.tasks.retry_failed_publish_job",
            "schedule": 300.0,
        },
        "sync-facebook-metrics": {
            "task": "app.workers.tasks.sync_facebook_metrics_job",
            "schedule": 3600.0,
        },
    },
)
