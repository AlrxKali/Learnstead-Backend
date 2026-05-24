from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from postgrest.exceptions import APIError
from supabase import Client

from app.dependencies import get_authenticated_supabase, get_current_user, get_supabase_admin
from app.schemas.businesses import (
    BusinessCategoryCreate,
    BusinessCategoryOut,
    BusinessCreate,
    BusinessOut,
    BusinessSubcategoriesSet,
    BusinessSubcategoryCreate,
    BusinessSubcategoryLinkBody,
    BusinessSubcategoryOut,
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


@router.post(
    "/categories",
    response_model=BusinessCategoryOut,
    status_code=status.HTTP_201_CREATED,
)
def create_category(
    body: BusinessCategoryCreate,
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_admin),
):
    try:
        response = (
            supabase.table("business_categories")
            .insert(body.model_dump(mode="json"))
            .execute()
        )
    except APIError as e:
        if e.code == "23505":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A category with this name already exists",
            ) from e
        raise
    return response.data[0]


@router.get("/subcategories", response_model=list[BusinessSubcategoryOut])
def list_subcategories(
    category_id: UUID | None = Query(None),
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_authenticated_supabase),
):
    if category_id is not None:
        # Get subcategory IDs linked to this category
        links = (
            supabase.table("business_category_subcategory")
            .select("subcategory_id")
            .eq("category_id", str(category_id))
            .execute()
        )
        sub_ids = [link["subcategory_id"] for link in links.data]
        if not sub_ids:
            return []
        rows = (
            supabase.table("business_subcategories")
            .select("*, business_category_subcategory(category_id, business_categories(*))")
            .in_("id", sub_ids)
            .execute()
        )
    else:
        rows = (
            supabase.table("business_subcategories")
            .select("*, business_category_subcategory(category_id, business_categories(*))")
            .execute()
        )
    return [_format_subcategory(row) for row in rows.data]


@router.post(
    "/subcategories",
    response_model=BusinessSubcategoryOut,
    status_code=status.HTTP_201_CREATED,
)
def create_subcategory(
    body: BusinessSubcategoryCreate,
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_admin),
):
    try:
        response = (
            supabase.table("business_subcategories")
            .insert({"name": body.name})
            .execute()
        )
    except APIError as e:
        if e.code == "23505":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A subcategory with this name already exists",
            ) from e
        raise
    subcategory = response.data[0]

    # Link to categories if provided
    if body.category_ids:
        link_rows = [
            {"category_id": str(cid), "subcategory_id": subcategory["id"]}
            for cid in body.category_ids
        ]
        try:
            supabase.table("business_category_subcategory").insert(link_rows).execute()
        except APIError as e:
            if e.code == "23503":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="One or more category_ids do not exist",
                ) from e
            raise

    return _fetch_subcategory_with_categories(supabase, subcategory["id"])


@router.post(
    "/categories/{category_id}/subcategories",
    response_model=BusinessSubcategoryOut,
    status_code=status.HTTP_201_CREATED,
)
def link_subcategory_to_category(
    category_id: UUID,
    body: BusinessSubcategoryLinkBody,
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_admin),
):
    try:
        supabase.table("business_category_subcategory").insert(
            {"category_id": str(category_id), "subcategory_id": str(body.subcategory_id)}
        ).execute()
    except APIError as e:
        if e.code == "23505":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This subcategory is already linked to this category",
            ) from e
        if e.code == "23503":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Category or subcategory does not exist",
            ) from e
        raise

    return _fetch_subcategory_with_categories(supabase, str(body.subcategory_id))


@router.delete(
    "/categories/{category_id}/subcategories/{subcategory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def unlink_subcategory_from_category(
    category_id: UUID,
    subcategory_id: UUID,
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_admin),
):
    response = (
        supabase.table("business_category_subcategory")
        .delete()
        .eq("category_id", str(category_id))
        .eq("subcategory_id", str(subcategory_id))
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link not found",
        )


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

    return _enrich(supabase, response.data[0])


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
    return _enrich_with_subcategories(supabase, row)


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

    # Merge with current row so we can validate the address rule
    # against the post-update state.
    existing_resp = (
        supabase.table("businesses")
        .select("delivery_mode, city, state, zip_code")
        .eq("owner_id", str(user.id))
        .execute()
    )
    if not existing_resp.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found",
        )
    merged = {**existing_resp.data[0], **updates}
    if merged.get("delivery_mode") in ("in_person", "hybrid"):
        missing = [
            label
            for label in ("city", "state", "zip_code")
            if not merged.get(label) or not str(merged[label]).strip()
        ]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "city, state, and zip_code are required for "
                    f"{merged['delivery_mode']} businesses "
                    f"(missing: {', '.join(missing)})"
                ),
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

    return _enrich(supabase, response.data[0])


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


@router.put("/me/subcategories", response_model=BusinessOut)
def set_my_subcategories(
    body: BusinessSubcategoriesSet,
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_authenticated_supabase),
):
    biz_resp = (
        supabase.table("businesses")
        .select("id")
        .eq("owner_id", str(user.id))
        .execute()
    )
    if not biz_resp.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found",
        )
    business_id = biz_resp.data[0]["id"]

    # Replace the set: delete existing links, insert the new ones.
    supabase.table("business_subcategory").delete().eq(
        "business_id", business_id
    ).execute()

    if body.subcategory_ids:
        rows = [
            {"business_id": business_id, "subcategory_id": str(sid)}
            for sid in body.subcategory_ids
        ]
        try:
            supabase.table("business_subcategory").insert(rows).execute()
        except APIError as e:
            if e.code == "23503":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="One or more subcategory_ids do not exist",
                ) from e
            raise

    full = (
        supabase.table("businesses")
        .select("*")
        .eq("id", business_id)
        .execute()
    )
    return _enrich(supabase, full.data[0])


def _format_subcategory(row: dict) -> dict:
    categories = []
    for link in row.pop("business_category_subcategory", []):
        cat = link.get("business_categories")
        if cat:
            categories.append(cat)
    row["categories"] = categories
    return row


def _fetch_subcategory_with_categories(supabase: Client, subcategory_id: str) -> dict:
    response = (
        supabase.table("business_subcategories")
        .select("*, business_category_subcategory(category_id, business_categories(*))")
        .eq("id", subcategory_id)
        .execute()
    )
    return _format_subcategory(response.data[0])


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


def _enrich_with_subcategories(supabase: Client, row: dict) -> dict:
    links = (
        supabase.table("business_subcategory")
        .select("subcategory_id, business_subcategories(*)")
        .eq("business_id", row["id"])
        .execute()
    )
    subcategories: list[dict] = []
    for link in links.data or []:
        sub = link.get("business_subcategories")
        if sub:
            subcategories.append(sub)
    row["subcategories"] = subcategories
    return row


def _enrich(supabase: Client, row: dict) -> dict:
    row = _enrich_with_category(supabase, row)
    return _enrich_with_subcategories(supabase, row)
