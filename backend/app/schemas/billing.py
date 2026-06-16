from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PaymentRequestCreate(BaseModel):
    plan_code: str = Field(min_length=2, max_length=60)
    payment_method: str = Field(default="bank_transfer", max_length=50)
    bank_name: str | None = Field(default=None, max_length=120)
    reference_number: str | None = Field(default=None, max_length=255)
    transfer_date: date | None = None
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("bank_name", "reference_number", "note")
    @classmethod
    def strip_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        return stripped or None

    @field_validator("plan_code", "payment_method")
    @classmethod
    def strip_required_strings(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) < 2:
            raise ValueError("Value is too short")
        return stripped


class PaymentRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    plan_code: str
    amount: int
    payment_method: str
    bank_name: str | None
    reference_number: str | None
    transfer_date: date | None
    note: str | None
    status: str
    reject_reason: str | None
    reviewed_by_id: int | None
    reviewed_at: datetime | None
    created_at: datetime
    account_name: str | None = None


class RejectRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def require_non_empty_reason(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Rejection reason is required")
        return stripped
