from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PublishLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int | None
    post_id: int
    page_id: int | None
    status: str
    request_payload: dict
    response_payload: dict
    error_message: str | None
    fb_post_id: str | None
    attempted_at: datetime
    created_at: datetime


class DashboardSummary(BaseModel):
    post_status_counts: dict[str, int]
    calendar_status_counts: dict[str, int]
    upcoming_posts: int
    failed_publishes: int
    latest_publish_logs: list[PublishLogRead]
