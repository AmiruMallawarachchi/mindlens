"""Administrative login and user-list routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import settings
from app.db import get_db
from app.middleware.auth import create_admin_token, get_rate_limit_store, require_user
from app.routers.auth_helpers import verify_password
from app.routers.auth_schemas import AdminLoginRequest, AdminTokenResponse

router = APIRouter()
# --- Admin Endpoints ---


@router.post(
    "/admin/login",
    response_model=AdminTokenResponse,
    summary="Admin login (separate token system)",
)
async def admin_login(
    request: AdminLoginRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Admin login with separate JWT secret.

    - Validates email + password
    - Requires role == 'admin'
    - Returns short-lived admin token (1 hour)
    """
    # Check lockout
    lockout_key = f"login:{request.email}"
    locked = await get_rate_limit_store().is_locked_out(
        lockout_key, max_attempts=settings.RATE_LIMIT_MAX_LOGIN_ATTEMPTS
    )
    if locked:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Try again in 15 minutes.",
        )

    user = await db.users.find_one({"email": request.email})
    if not user:
        await get_rate_limit_store().record_login_attempt(lockout_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not verify_password(request.password, user["password_hash"]):
        await get_rate_limit_store().record_login_attempt(lockout_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if user.get("role") != settings.ADMIN_ROLE_NAME:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    await get_rate_limit_store().reset_login_attempts(lockout_key)

    user_id = str(user["_id"])
    admin_token = create_admin_token(user_id, request.email)

    return AdminTokenResponse(
        admin_token=admin_token,
        token_type="bearer",
        expires_in=settings.admin_jwt_expire_minutes * 60,
    )


@router.get(
    "/users/count",
    summary="Get total user count (admin only)",
)
async def get_user_count(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_user),
):
    """
    Return total number of registered users.

    Protected: requires valid authentication. Admin role enforced at query level.
    """
    if current_user.get("role") != settings.ADMIN_ROLE_NAME:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    count = await db.users.count_documents({})
    return {"total_users": count}


@router.get(
    "/users/list",
    summary="List all users (admin only)",
)
async def list_users(
    skip: int = 0,
    limit: int = 50,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_user),
):
    """List all users (admin only)."""
    if current_user.get("role") != settings.ADMIN_ROLE_NAME:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    cursor = db.users.find({}).skip(skip).limit(limit)
    users = []
    async for doc in cursor:
        users.append({
            "id": str(doc["_id"]),
            "email": doc["email"],
            "name": doc["name"],
            "age_group": doc.get("age_group"),
            "role": doc.get("role", "user"),
            "onboarding_complete": doc.get("onboarding_complete", False),
            "created_at": doc.get("created_at"),
        })
    return {"users": users, "count": len(users)}

