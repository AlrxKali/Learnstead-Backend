from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class BusinessCategoryCreate(BaseModel):
    name: str


class BusinessCategoryOut(BaseModel):
    id: UUID
    name: str


class BusinessSubcategoryCreate(BaseModel):
    name: str
    category_ids: list[UUID] = []


class BusinessSubcategoryOut(BaseModel):
    id: UUID
    name: str
    categories: list[BusinessCategoryOut] = []


class BusinessSubcategoryLinkBody(BaseModel):
    subcategory_id: UUID


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
