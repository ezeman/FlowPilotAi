from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class SubscriptionPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    description: str | None
    price_monthly: int
    max_pages: int
    max_users: int
    max_auto_ideas_per_day: int
    is_active: bool


class AccountSubscriptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    starts_at: datetime | None
    expires_at: datetime | None
    auto_renew: bool
    plan: SubscriptionPlanRead


class AccountUsageRead(BaseModel):
    pages_used: int = 0
    users_used: int = 0
    posts_used: int = 0
    ideas_used: int = 0


class AccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    is_active: bool
    created_by_id: int | None
    created_at: datetime
    updated_at: datetime
    active_subscription: AccountSubscriptionRead | None = None
    usage: AccountUsageRead = Field(default_factory=AccountUsageRead)


class AccountCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    slug: str = Field(min_length=2, max_length=120)
    plan_code: str = Field(default="starter", min_length=2, max_length=60)


class AccountSubscriptionUpdate(BaseModel):
    plan_code: str = Field(min_length=2, max_length=60)
    status: str = Field(default="active", min_length=2, max_length=50)
    expires_at: datetime | None = None
    auto_renew: bool = False


class ManagedUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int | None
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
    is_email_verified: bool
    created_at: datetime
    updated_at: datetime
    assigned_page_ids: list[int] = Field(default_factory=list)


class ManagedUserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(default="editor", min_length=2, max_length=50)
    account_id: int | None = None
    is_active: bool = True
    assigned_page_ids: list[int] = Field(default_factory=list)

    @field_validator("role")
    @classmethod
    def normalize_role(cls, value: str) -> str:
        return "platform_owner" if value == "platform_admin" else value


class ManagedUserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    role: str | None = Field(default=None, min_length=2, max_length=50)
    is_active: bool | None = None
    assigned_page_ids: list[int] | None = None

    @field_validator("role")
    @classmethod
    def normalize_role(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return "platform_owner" if value == "platform_admin" else value
