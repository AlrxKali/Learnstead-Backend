from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, model_validator


SessionStatus = Literal["planned", "cancelled"]


class _BusinessSummary(BaseModel):
    id: UUID
    name: str


class PlanCreate(BaseModel):
    title: str
    notes: str | None = None
    business_id: UUID | None = None
    color: str | None = None


class PlanUpdate(BaseModel):
    title: str | None = None
    notes: str | None = None
    business_id: UUID | None = None
    color: str | None = None


class PlanOut(BaseModel):
    id: UUID
    parent_id: UUID
    business_id: UUID | None = None
    business: _BusinessSummary | None = None
    title: str
    notes: str | None = None
    color: str
    created_at: datetime
    updated_at: datetime


class PlanSessionCreate(BaseModel):
    starts_at: datetime
    ends_at: datetime
    notes: str | None = None

    @model_validator(mode="after")
    def _check_times(self) -> "PlanSessionCreate":
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class PlanSessionUpdate(BaseModel):
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    notes: str | None = None
    status: SessionStatus | None = None

    @model_validator(mode="after")
    def _check_times(self) -> "PlanSessionUpdate":
        # Both must be present together if updating, OR caller updates only
        # one (validated against the existing row at the router).
        if (
            self.starts_at is not None
            and self.ends_at is not None
            and self.ends_at <= self.starts_at
        ):
            raise ValueError("ends_at must be after starts_at")
        return self


class PlanSessionOut(BaseModel):
    id: UUID
    plan_id: UUID
    starts_at: datetime
    ends_at: datetime
    status: SessionStatus
    notes: str | None = None
    created_at: datetime
