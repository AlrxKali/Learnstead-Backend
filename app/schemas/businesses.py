from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class BusinessCategoryOut(BaseModel):
    id: UUID
    name: str


class BusinessCreate(BaseModel):
    name: str
    description: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    category_id: UUID | None = None


class BusinessUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    category_id: UUID | None = None


class BusinessOut(BaseModel):
    id: UUID
    owner_id: UUID
    name: str
    description: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    category_id: UUID | None = None
    category: BusinessCategoryOut | None = None
    created_at: datetime
    updated_at: datetime
