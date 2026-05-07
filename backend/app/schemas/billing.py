from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class PaymentRequestCreate(BaseModel):
    plan_code: str = Field(min_length=2, max_length=60)
    payment_method: str = Field(default="bank_transfer", max_length=50)
    bank_name: str | None = Field(default=None, max_length=120)
    reference_number: str | None = Field(default=None, max_length=255)
    transfer_date: date | None = None
    note: str | None = Field(default=None, max_length=1000)


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
