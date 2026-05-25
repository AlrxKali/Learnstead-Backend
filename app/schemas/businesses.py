import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, field_validator, model_validator

from app.schemas._validators import normalize_us_zip

DeliveryMode = Literal["online", "in_person", "hybrid"]


def _normalize_us_phone(value: str | None) -> str | None:
    """Accept any input, return E.164 (+1XXXXXXXXXX) or None.

    Rejects anything that isn't a valid 10-digit US number (optionally
    prefixed with 1 or +1).
    """
    if value is None:
        return None
    raw = str(value).strip()
    if raw == "":
        return None
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    raise ValueError("Phone must be a valid US number (10 digits)")


def _validate_age_pair(min_age: int | None, max_age: int | None) -> None:
    for label, val in (("min_age", min_age), ("max_age", max_age)):
        if val is not None and (val < 0 or val > 99):
            raise ValueError(f"{label} must be between 0 and 99")
    if min_age is not None and max_age is not None and min_age > max_age:
        raise ValueError("min_age must be less than or equal to max_age")


def _validate_address_for_mode(
    delivery_mode: DeliveryMode | None,
    city: str | None,
    state: str | None,
    zip_code: str | None,
) -> None:
    if delivery_mode in ("in_person", "hybrid"):
        missing = [
            label
            for label, val in (("city", city), ("state", state), ("zip_code", zip_code))
            if not val or not str(val).strip()
        ]
        if missing:
            raise ValueError(
                f"city, state, and zip_code are required for {delivery_mode} businesses "
                f"(missing: {', '.join(missing)})"
            )


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


class BusinessSubcategoriesSet(BaseModel):
    subcategory_ids: list[UUID]


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
    delivery_mode: DeliveryMode = "in_person"
    min_age: int | None = None
    max_age: int | None = None

    @field_validator("phone", mode="before")
    @classmethod
    def _normalize_phone(cls, v: str | None) -> str | None:
        return _normalize_us_phone(v)

    @field_validator("zip_code", mode="before")
    @classmethod
    def _normalize_zip(cls, v: str | None) -> str | None:
        return normalize_us_zip(v)

    @model_validator(mode="after")
    def _check_consistency(self) -> "BusinessCreate":
        _validate_age_pair(self.min_age, self.max_age)
        _validate_address_for_mode(
            self.delivery_mode, self.city, self.state, self.zip_code
        )
        return self


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
    delivery_mode: DeliveryMode | None = None
    min_age: int | None = None
    max_age: int | None = None

    @field_validator("phone", mode="before")
    @classmethod
    def _normalize_phone(cls, v: str | None) -> str | None:
        return _normalize_us_phone(v)

    @field_validator("zip_code", mode="before")
    @classmethod
    def _normalize_zip(cls, v: str | None) -> str | None:
        return normalize_us_zip(v)

    @model_validator(mode="after")
    def _check_age_pair(self) -> "BusinessUpdate":
        # Address rule can't be enforced here without the existing row
        # (the update is partial). The router merges with current state.
        _validate_age_pair(self.min_age, self.max_age)
        return self


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
    delivery_mode: DeliveryMode
    min_age: int | None = None
    max_age: int | None = None
    subcategories: list[BusinessCategoryOut] = []
    created_at: datetime
    updated_at: datetime
