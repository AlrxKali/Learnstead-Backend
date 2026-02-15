from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr


class SignUpRequest(BaseModel):
    email: str
    password: str
    role: str  # "parent" or "provider"
    full_name: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class ProfileOut(BaseModel):
    id: UUID
    role: str
    full_name: str | None = None
    created_at: datetime


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: ProfileOut
