from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.tenant import AccountSubscriptionRead, SubscriptionPlanRead


class SettingUpsert(BaseModel):
    key: str = Field(min_length=2, max_length=120)
    value_text: str | None = None
    value_json: dict | list | None = None
    description: str | None = Field(default=None, max_length=500)

    @field_validator("key")
    @classmethod
    def normalize_key(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def require_one_value(self) -> "SettingUpsert":
        if self.value_text is not None and self.value_json is not None:
            raise ValueError("Send either value_text or value_json, not both")
        return self


class SettingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int | None
    key: str
    value_text: str | None
    value_json: dict | list | None
    is_encrypted: bool
    description: str | None
    updated_by_id: int | None
    created_at: datetime
    updated_at: datetime


class SettingsDocument(BaseModel):
    account: dict[str, str | list[str]]
    platform: dict[str, str | list[str] | bool] | None = None


class SettingsPatch(BaseModel):
    default_tone: str | None = Field(default=None, max_length=80)
    content_pillars: list[str] | None = None
    openai_api_key: str | None = Field(default=None, max_length=500)

    @field_validator("default_tone")
    @classmethod
    def normalize_tone(cls, value: str | None) -> str | None:
        return value.strip() if value else value

    @field_validator("content_pillars")
    @classmethod
    def validate_pillars(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        cleaned = [item.strip() for item in value if item and item.strip()]
        if len(cleaned) != len(value) or not cleaned:
            raise ValueError("Content pillars cannot contain empty values")
        return cleaned

    @field_validator("openai_api_key")
    @classmethod
    def normalize_secret(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return value.strip()


class UsageOverview(BaseModel):
    has_active_subscription: bool
    subscription: AccountSubscriptionRead | None = None
    plan: SubscriptionPlanRead | None = None
    pages_used: int
    users_used: int
    auto_ideas_used_today: int
    max_pages: int
    max_users: int
    max_auto_ideas_per_day: int
