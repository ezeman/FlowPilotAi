from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.schemas.tenant import AccountRead


def _validate_password_complexity(v: str) -> str:
    errors = []
    if not re.search(r"[A-Z]", v):
        errors.append("ตัวพิมพ์ใหญ่อย่างน้อย 1 ตัว")
    if not re.search(r"[a-z]", v):
        errors.append("ตัวพิมพ์เล็กอย่างน้อย 1 ตัว")
    if not re.search(r"\d", v):
        errors.append("ตัวเลขอย่างน้อย 1 ตัว")
    if errors:
        raise ValueError("รหัสผ่านต้องมี: " + ", ".join(errors))
    return v


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class BootstrapAdminRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class RegisterRequest(BaseModel):
    account_name: str = Field(min_length=2, max_length=255)
    full_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        return _validate_password_complexity(v)

    @model_validator(mode="after")
    def passwords_match(self) -> "RegisterRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        return _validate_password_complexity(v)


class RegisterResponse(BaseModel):
    message: str
    verification_token: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int | None
    active_account_id: int | None = None
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
    is_email_verified: bool
    account: AccountRead | None = None
