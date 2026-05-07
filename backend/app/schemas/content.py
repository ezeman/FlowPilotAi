from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


POST_STATUSES = {
    "idea",
    "generating",
    "draft",
    "ready_for_review",
    "approved",
    "scheduled",
    "publishing",
    "posted",
    "failed",
}


class CalendarBase(BaseModel):
    account_id: int | None = None
    title: str = Field(min_length=3, max_length=255)
    topic: str = Field(min_length=3, max_length=255)
    content_pillar: str = Field(min_length=2, max_length=120)
    target_audience: str | None = Field(default=None, max_length=255)
    tone: str | None = Field(default=None, max_length=120)
    post_length: str = Field(default="medium", max_length=50)
    status: str = Field(default="idea", max_length=50)
    scheduled_date: date | None = None
    notes: str | None = None


class CalendarCreate(CalendarBase):
    pass


class CalendarUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=255)
    topic: str | None = Field(default=None, min_length=3, max_length=255)
    content_pillar: str | None = Field(default=None, min_length=2, max_length=120)
    target_audience: str | None = Field(default=None, max_length=255)
    tone: str | None = Field(default=None, max_length=120)
    post_length: str | None = Field(default=None, max_length=50)
    status: str | None = Field(default=None, max_length=50)
    scheduled_date: date | None = None
    notes: str | None = None


class CalendarRead(CalendarBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_by_id: int | None
    created_at: datetime
    updated_at: datetime


class TrustedSourceRead(BaseModel):
    id: str
    name: str
    url: str
    content_pillar: str
    source_type: str = "official_web"


class AutoIdeaDiscoveryRequest(BaseModel):
    count: int = Field(default=5, ge=1, le=10)
    save_to_calendar: bool = True


class AutoIdeaDiscoveryItem(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    topic: str = Field(min_length=3, max_length=255)
    content_pillar: str = Field(min_length=2, max_length=120)
    target_audience: str | None = Field(default=None, max_length=255)
    tone: str | None = Field(default=None, max_length=120)
    post_length: str = Field(default="medium", max_length=50)
    notes: str | None = None
    source_name: str
    source_url: str


class AutoIdeaDiscoveryResponse(BaseModel):
    items: list[CalendarRead | AutoIdeaDiscoveryItem]
    sources_checked: list[TrustedSourceRead]


class AutoIdeaScheduleConfig(BaseModel):
    enabled: bool = False
    time_local: str = Field(default="09:00", pattern=r"^\d{2}:\d{2}$")
    count: int = Field(default=5, ge=1, le=10)


class AutoIdeaScheduleState(BaseModel):
    last_run_local_date: str | None = None


class AutoIdeaScheduleResponse(BaseModel):
    config: AutoIdeaScheduleConfig
    state: AutoIdeaScheduleState


class PostAssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_type: str
    asset_url: str
    alt_text: str | None
    metadata_json: dict


class ReferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    source_url: str | None
    note: str | None
    source_type: str


class PostBase(BaseModel):
    account_id: int | None = None
    calendar_id: int | None = None
    page_id: int | None = None
    title: str = Field(min_length=3, max_length=255)
    caption: str | None = None
    hashtags: list[str] = Field(default_factory=list)
    image_prompt: str | None = None
    content_pillar: str = Field(min_length=2, max_length=120)
    target_audience: str | None = Field(default=None, max_length=255)
    tone: str | None = Field(default=None, max_length=120)
    post_length: str = Field(default="medium", max_length=50)
    status: str = Field(default="idea", max_length=50)
    reference_notes: str | None = None
    scheduled_for: datetime | None = None


class PostCreate(PostBase):
    pass


class PostUpdate(BaseModel):
    calendar_id: int | None = None
    page_id: int | None = None
    title: str | None = Field(default=None, min_length=3, max_length=255)
    caption: str | None = None
    hashtags: list[str] | None = None
    image_prompt: str | None = None
    content_pillar: str | None = Field(default=None, min_length=2, max_length=120)
    target_audience: str | None = Field(default=None, max_length=255)
    tone: str | None = Field(default=None, max_length=120)
    post_length: str | None = Field(default=None, max_length=50)
    status: str | None = Field(default=None, max_length=50)
    reference_notes: str | None = None
    scheduled_for: datetime | None = None


class PostRead(PostBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    approved_by_id: int | None
    approved_at: datetime | None
    quality_score: int | None
    fb_post_id: str | None
    last_error: str | None
    created_by_id: int | None
    created_at: datetime
    updated_at: datetime
    assets: list[PostAssetRead] = Field(default_factory=list)
    references: list[ReferenceRead] = Field(default_factory=list)


class GenerateContentRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=255)
    content_pillar: str = Field(min_length=2, max_length=120)
    target_audience: str = Field(min_length=2, max_length=255)
    tone: str = Field(min_length=2, max_length=120)
    post_length: str = Field(default="medium", max_length=50)
    reference_notes: str | None = None
    post_id: int | None = None


class GenerateContentResponse(BaseModel):
    title: str
    caption: str
    hashtags: list[str]
    image_prompt: str
    reference_suggestions: list[str]
    quality_score: int


class ImageGenerationRequest(BaseModel):
    variant_count: int = Field(default=1, ge=1, le=4)


class SchedulePostRequest(BaseModel):
    scheduled_for: datetime


class ReviewDecisionRequest(BaseModel):
    approved: bool
    notes: str | None = None


class PageBase(BaseModel):
    account_id: int | None = None
    name: str = Field(min_length=2, max_length=255)
    facebook_page_id: str = Field(min_length=2, max_length=255)
    page_category: str | None = Field(default=None, max_length=255)
    description: str | None = None
    is_active: bool = True
    access_token: str | None = None


class PageCreate(PageBase):
    pass


class PageUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    facebook_page_id: str | None = Field(default=None, min_length=2, max_length=255)
    page_category: str | None = Field(default=None, max_length=255)
    description: str | None = None
    is_active: bool | None = None
    access_token: str | None = None


class PageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    name: str
    facebook_page_id: str
    page_category: str | None
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
