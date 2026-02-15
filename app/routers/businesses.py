from fastapi import APIRouter, Depends, HTTPException, status
from postgrest.exceptions import APIError
from supabase import Client

from app.dependencies import get_authenticated_supabase, get_current_user
from app.schemas.businesses import (
    BusinessCategoryOut,
    BusinessCreate,
    BusinessOut,
    BusinessUpdate,
)

router = APIRouter(prefix="/businesses", tags=["businesses"])


@router.get("/categories", response_model=list[BusinessCategoryOut])
def list_categories(
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_authenticated_supabase),
):
    response = supabase.table("business_categories").select("*").execute()
    return response.data


@router.post("", response_model=BusinessOut, status_code=status.HTTP_201_CREATED)
def create_business(
    body: BusinessCreate,
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_authenticated_supabase),
):
    # Check if user already has a business
    existing = (
        supabase.table("businesses")
        .select("id")
        .eq("owner_id", str(user.id))
        .execute()
    )
    if existing.data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have a business profile",
        )

    data = body.model_dump(exclude_none=True, mode="json")
    data["owner_id"] = str(user.id)

    try:
        response = (
            supabase.table("businesses")
            .insert(data)
            .execute()
        )
    except APIError as e:
        if e.code == "23503":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid category_id: category does not exist",
            ) from e
        raise

    return _enrich_with_category(supabase, response.data[0])


@router.get("/me", response_model=BusinessOut)
def get_my_business(
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_authenticated_supabase),
):
    response = (
        supabase.table("businesses")
        .select("*, business_categories(*)")
        .eq("owner_id", str(user.id))
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found",
        )

    row = response.data[0]
    row["category"] = row.pop("business_categories", None)
    return row


@router.put("/me", response_model=BusinessOut)
def update_my_business(
    body: BusinessUpdate,
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
            supabase.table("businesses")
            .update(updates)
            .eq("owner_id", str(user.id))
            .execute()
        )
    except APIError as e:
        if e.code == "23503":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid category_id: category does not exist",
            ) from e
        raise
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found",
        )

    return _enrich_with_category(supabase, response.data[0])


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_business(
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_authenticated_supabase),
):
    response = (
        supabase.table("businesses")
        .delete()
        .eq("owner_id", str(user.id))
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found",
        )


def _enrich_with_category(supabase: Client, row: dict) -> dict:
    if row.get("category_id"):
        cat = (
            supabase.table("business_categories")
            .select("*")
            .eq("id", row["category_id"])
            .execute()
        )
        row["category"] = cat.data[0] if cat.data else None
    else:
        row["category"] = None
    return row
