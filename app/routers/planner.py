from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from postgrest.exceptions import APIError
from supabase import Client

from app.dependencies import get_authenticated_supabase, get_current_user
from app.schemas.planner import (
    PlanCreate,
    PlanOut,
    PlanSessionCreate,
    PlanSessionOut,
    PlanSessionUpdate,
    PlanUpdate,
)

router = APIRouter(tags=["planner"])


# ---------- plans ----------


@router.get("/plans", response_model=list[PlanOut])
def list_plans(
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_authenticated_supabase),
):
    rows = (
        supabase.table("plans")
        .select("*, businesses(id, name)")
        .eq("parent_id", str(user.id))
        .order("created_at", desc=True)
        .execute()
        .data
    )
    return [_format_plan(row) for row in rows]


@router.post("/plans", response_model=PlanOut, status_code=status.HTTP_201_CREATED)
def create_plan(
    body: PlanCreate,
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_authenticated_supabase),
):
    data = body.model_dump(exclude_none=True, mode="json")
    data["parent_id"] = str(user.id)
    try:
        response = supabase.table("plans").insert(data).execute()
    except APIError as e:
        if e.code == "23503":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="business_id does not exist",
            ) from e
        raise
    return _format_plan(_fetch_plan_with_business(supabase, response.data[0]["id"]))


@router.patch("/plans/{plan_id}", response_model=PlanOut)
def update_plan(
    plan_id: UUID,
    body: PlanUpdate,
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_authenticated_supabase),
):
    updates = body.model_dump(exclude_unset=True, mode="json")
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )
    try:
        response = (
            supabase.table("plans")
            .update(updates)
            .eq("id", str(plan_id))
            .eq("parent_id", str(user.id))
            .execute()
        )
    except APIError as e:
        if e.code == "23503":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="business_id does not exist",
            ) from e
        raise
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found"
        )
    return _format_plan(_fetch_plan_with_business(supabase, str(plan_id)))


@router.delete("/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan(
    plan_id: UUID,
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_authenticated_supabase),
):
    response = (
        supabase.table("plans")
        .delete()
        .eq("id", str(plan_id))
        .eq("parent_id", str(user.id))
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found"
        )


# ---------- sessions ----------


@router.get("/sessions", response_model=list[PlanSessionOut])
def list_sessions(
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_authenticated_supabase),
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = Query(None),
    plan_id: UUID | None = Query(None),
):
    # Plans the user owns — used as the membership gate. Cheap query.
    plans_resp = (
        supabase.table("plans")
        .select("id")
        .eq("parent_id", str(user.id))
        .execute()
    )
    plan_ids = [p["id"] for p in plans_resp.data or []]
    if not plan_ids:
        return []

    query = supabase.table("plan_sessions").select("*").in_("plan_id", plan_ids)
    if plan_id is not None:
        query = query.eq("plan_id", str(plan_id))
    if from_ is not None:
        query = query.gte("starts_at", from_.isoformat())
    if to is not None:
        query = query.lte("starts_at", to.isoformat())
    return query.order("starts_at").execute().data


@router.post(
    "/plans/{plan_id}/sessions",
    response_model=PlanSessionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_session(
    plan_id: UUID,
    body: PlanSessionCreate,
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_authenticated_supabase),
):
    _assert_plan_owned(supabase, plan_id, user.id)
    data = body.model_dump(mode="json")
    data["plan_id"] = str(plan_id)
    response = supabase.table("plan_sessions").insert(data).execute()
    return response.data[0]


@router.patch("/sessions/{session_id}", response_model=PlanSessionOut)
def update_session(
    session_id: UUID,
    body: PlanSessionUpdate,
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_authenticated_supabase),
):
    updates = body.model_dump(exclude_unset=True, mode="json")
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    # Cross-field consistency: if only one of starts/ends is changing,
    # validate against the existing value.
    if ("starts_at" in updates) != ("ends_at" in updates):
        existing = (
            supabase.table("plan_sessions")
            .select("starts_at, ends_at")
            .eq("id", str(session_id))
            .execute()
        )
        if not existing.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
            )
        row = {**existing.data[0], **updates}
        if datetime.fromisoformat(row["ends_at"]) <= datetime.fromisoformat(
            row["starts_at"]
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ends_at must be after starts_at",
            )

    response = (
        supabase.table("plan_sessions")
        .update(updates)
        .eq("id", str(session_id))
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    return response.data[0]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: UUID,
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_authenticated_supabase),
):
    response = (
        supabase.table("plan_sessions")
        .delete()
        .eq("id", str(session_id))
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )


# ---------- helpers ----------


def _assert_plan_owned(supabase: Client, plan_id: UUID, user_id) -> None:
    resp = (
        supabase.table("plans")
        .select("id")
        .eq("id", str(plan_id))
        .eq("parent_id", str(user_id))
        .execute()
    )
    if not resp.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found"
        )


def _fetch_plan_with_business(supabase: Client, plan_id) -> dict:
    return (
        supabase.table("plans")
        .select("*, businesses(id, name)")
        .eq("id", str(plan_id))
        .execute()
        .data[0]
    )


def _format_plan(row: dict) -> dict:
    biz = row.pop("businesses", None)
    row["business"] = biz if biz else None
    return row
