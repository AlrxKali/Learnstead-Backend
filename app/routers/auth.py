from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from app.dependencies import get_authenticated_supabase, get_current_user, get_supabase, get_supabase_admin
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    ProfileOut,
    ProfileUpdate,
    SignUpRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])

VALID_ROLES = {"parent", "provider"}


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(
    body: SignUpRequest,
    supabase: Client = Depends(get_supabase),
    supabase_admin: Client = Depends(get_supabase_admin),
):
    if body.role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Must be one of: {', '.join(VALID_ROLES)}",
        )

    if body.role == "parent" and not body.home_zip_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Home zip code is required for parents.",
        )

    # Create the auth user via Supabase
    try:
        auth_response = supabase.auth.sign_up(
            {"email": body.email, "password": body.password}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    if not auth_response.user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Signup failed",
        )

    # Insert profile row using service_role client (bypasses RLS)
    user_id = str(auth_response.user.id)
    profile_data = {
        "id": user_id,
        "role": body.role,
        "full_name": body.full_name,
        "home_zip_code": body.home_zip_code,
    }

    try:
        profile_response = (
            supabase_admin.table("profiles").insert(profile_data).execute()
        )
    except Exception as e:
        # Clean up: delete the auth user if profile creation fails
        supabase_admin.auth.admin.delete_user(user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user profile",
        ) from e

    profile = profile_response.data[0]

    return AuthResponse(
        access_token=auth_response.session.access_token,
        refresh_token=auth_response.session.refresh_token,
        user=ProfileOut(**profile),
    )


@router.post("/login", response_model=AuthResponse)
def login(
    body: LoginRequest,
    supabase: Client = Depends(get_supabase),
):
    try:
        auth_response = supabase.auth.sign_in_with_password(
            {"email": body.email, "password": body.password}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        ) from e

    if not auth_response.user or not auth_response.session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Fetch the profile
    user_id = str(auth_response.user.id)
    profile_response = (
        supabase.table("profiles")
        .select("*")
        .eq("id", user_id)
        .execute()
    )

    if not profile_response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found",
        )

    profile = profile_response.data[0]

    return AuthResponse(
        access_token=auth_response.session.access_token,
        refresh_token=auth_response.session.refresh_token,
        user=ProfileOut(**profile),
    )


@router.get("/me", response_model=ProfileOut)
def get_me(
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_authenticated_supabase),
):
    response = (
        supabase.table("profiles")
        .select("*")
        .eq("id", str(user.id))
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )
    return response.data[0]


@router.patch("/me", response_model=ProfileOut)
def update_me(
    body: ProfileUpdate,
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_authenticated_supabase),
):
    updates = body.model_dump(exclude_unset=True, mode="json")
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )
    response = (
        supabase.table("profiles")
        .update(updates)
        .eq("id", str(user.id))
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )
    return response.data[0]
