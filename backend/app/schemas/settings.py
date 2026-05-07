from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SettingUpsert(BaseModel):
    key: str = Field(min_length=2, max_length=120)
    value_text: str | None = None
    value_json: dict | list | None = None
    description: str | None = Field(default=None, max_length=500)


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
