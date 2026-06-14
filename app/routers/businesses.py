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


@router.get("/search", response_model=list[BusinessOut])
def search_businesses(
    q: str | None = Query(None),
    category_id: UUID | None = Query(None),
    subcategory_id: list[UUID] | None = Query(None),
    delivery_mode: list[str] | None = Query(None),
    age: int | None = Query(None, ge=0, le=99),
    zip_prefix: str | None = Query(None, min_length=3, max_length=3),
    limit: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_authenticated_supabase),
):
    """Open-ended search over businesses.

    Differs from /discover by NOT applying parent's home_zip_code implicitly.
    Locality is opt-in via the explicit zip_prefix param.

    Filters (all optional, AND-combined):
      - q: case-insensitive substring match on name OR description
      - category_id: exact match
      - subcategory_id: business must link to ANY of these subcategories
      - delivery_mode: business must be one of these modes
      - age: program must serve this age (NULL bounds = open-ended)
      - zip_prefix: first 3 digits of zip must match (in_person / hybrid only;
        online businesses are always included)
    """
    # Subcategory pre-filter: collect matching business_ids first, since the
    # link lives in a junction table.
    business_id_filter: list[str] | None = None
    if subcategory_id:
        links = (
            supabase.table("business_subcategory")
            .select("business_id")
            .in_("subcategory_id", [str(s) for s in subcategory_id])
            .execute()
        )
        ids = list({row["business_id"] for row in links.data or []})
        if not ids:
            return []
        business_id_filter = ids

    query = supabase.table("businesses").select("*, business_categories(*)")

    if business_id_filter is not None:
        query = query.in_("id", business_id_filter)
    if category_id is not None:
        query = query.eq("category_id", str(category_id))
    if delivery_mode:
        query = query.in_("delivery_mode", delivery_mode)
    if age is not None:
        # min_age IS NULL OR min_age <= age
        query = query.or_(f"min_age.is.null,min_age.lte.{age}")
        # max_age IS NULL OR max_age >= age
        query = query.or_(f"max_age.is.null,max_age.gte.{age}")
    if q:
        like = f"*{q}*"
        query = query.or_(f"name.ilike.{like},description.ilike.{like}")
    if zip_prefix:
        # online is always included; in_person/hybrid must match zip prefix.
        query = query.or_(
            f"delivery_mode.eq.online,"
            f"and(delivery_mode.in.(in_person,hybrid),zip_code.like.{zip_prefix}*)"
        )

    rows = (
        query.order("created_at", desc=True)
        .limit(limit)
        .execute()
        .data
    )

    out: list[dict] = []
    for row in rows:
        row["category"] = row.pop("business_categories", None)
        out.append(_enrich_with_subcategories(supabase, row))
    return out


@router.get("/discover", response_model=list[BusinessOut])
def discover_businesses(
    q: str | None = Query(None),
    category_id: UUID | None = Query(None),
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_authenticated_supabase),
):
    """Listing for parents.

    Returns:
      - All `delivery_mode = 'online'` businesses, AND
      - `in_person`/`hybrid` businesses whose zip_code shares the first 3
        digits with the requesting user's home_zip_code.

    If the user has no home_zip_code set, only online businesses are
    returned.

    Optional filters:
      - q: case-insensitive match on name OR description
      - category_id: exact match on the business category
    """
    profile_resp = (
        supabase.table("profiles")
        .select("home_zip_code")
        .eq("id", str(user.id))
        .execute()
    )
    home_zip = (
        profile_resp.data[0]["home_zip_code"] if profile_resp.data else None
    )
    zip_prefix = home_zip[:3] if home_zip else None

    query = supabase.table("businesses").select("*, business_categories(*)")

    if zip_prefix:
        # Online OR locality-matched in_person/hybrid.
        # PostgREST uses url-like 'or' syntax for this.
        query = query.or_(
            f"delivery_mode.eq.online,"
            f"and(delivery_mode.in.(in_person,hybrid),zip_code.like.{zip_prefix}*)"
        )
    else:
        query = query.eq("delivery_mode", "online")

    if category_id is not None:
        query = query.eq("category_id", str(category_id))
    if q:
        # Case-insensitive name or description match.
        like = f"*{q}*"
        query = query.or_(f"name.ilike.{like},description.ilike.{like}")

    rows = query.order("created_at", desc=True).execute().data

    out: list[dict] = []
    for row in rows:
        row["category"] = row.pop("business_categories", None)
        out.append(_enrich_with_subcategories(supabase, row))
    return out


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


@router.get("/saved", response_model=list[BusinessOut])
def list_saved(
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_authenticated_supabase),
):
    """Businesses the current user has saved, newest-saved first."""
    saved = (
        supabase.table("saved_businesses")
        .select("business_id, saved_at")
        .eq("parent_id", str(user.id))
        .order("saved_at", desc=True)
        .execute()
        .data
        or []
    )
    if not saved:
        return []
    ids = [row["business_id"] for row in saved]
    rows = (
        supabase.table("businesses")
        .select("*, business_categories(*)")
        .in_("id", ids)
        .execute()
        .data
        or []
    )
    # Preserve saved_at order.
    by_id = {r["id"]: r for r in rows}
    ordered = [by_id[i] for i in ids if i in by_id]
    out: list[dict] = []
    for r in ordered:
        r["category"] = r.pop("business_categories", None)
        out.append(_enrich_with_subcategories(supabase, r))
    return out


@router.get("/saved/ids", response_model=list[str])
def list_saved_ids(
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_authenticated_supabase),
):
    """Just the business IDs — used to know which heart icons to fill."""
    rows = (
        supabase.table("saved_businesses")
        .select("business_id")
        .eq("parent_id", str(user.id))
        .execute()
        .data
        or []
    )
    return [r["business_id"] for r in rows]


@router.put("/saved/{business_id}", status_code=status.HTTP_204_NO_CONTENT)
def save_business(
    business_id: UUID,
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_authenticated_supabase),
):
    try:
        supabase.table("saved_businesses").insert({
            "parent_id": str(user.id),
            "business_id": str(business_id),
        }).execute()
    except APIError as e:
        # Already saved (composite PK violation) is a no-op success.
        if e.code == "23505":
            return
        if e.code == "23503":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Business not found",
            ) from e
        raise


@router.delete("/saved/{business_id}", status_code=status.HTTP_204_NO_CONTENT)
def unsave_business(
    business_id: UUID,
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_authenticated_supabase),
):
    supabase.table("saved_businesses").delete().eq(
        "parent_id", str(user.id)
    ).eq("business_id", str(business_id)).execute()


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
