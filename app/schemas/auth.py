from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, field_validator

from app.schemas._validators import normalize_us_zip


class SignUpRequest(BaseModel):
    email: str
    password: str
    role: str  # "parent" or "provider"
    full_name: str | None = None
    home_zip_code: str | None = None

    @field_validator("home_zip_code", mode="before")
    @classmethod
    def _normalize_zip(cls, v: str | None) -> str | None:
        return normalize_us_zip(v)


class LoginRequest(BaseModel):
    email: str
    password: str


class ProfileUpdate(BaseModel):
    full_name: str | None = None
    home_zip_code: str | None = None

    @field_validator("home_zip_code", mode="before")
    @classmethod
    def _normalize_zip(cls, v: str | None) -> str | None:
        return normalize_us_zip(v)


class ProfileOut(BaseModel):
    id: UUID
    role: str
    full_name: str | None = None
    home_zip_code: str | None = None
    created_at: datetime


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: ProfileOut
