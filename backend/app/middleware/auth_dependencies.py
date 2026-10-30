"""FastAPI dependencies for user and admin authentication."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request, status
from jwt.exceptions import PyJWTError as JWTError
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import settings
from app.db import document_id_filter, get_db
from app.middleware.auth_tokens import (
    get_request_access_token,
    verify_access_token,
    verify_admin_token,
)

# ---------------------------------------------------------------------------
# FastAPI Dependencies
# ---------------------------------------------------------------------------




async def require_user(
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """
    FastAPI dependency: require valid user JWT.
    Returns user document from MongoDB.
    """
    token = get_request_access_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization token",
        )
    try:
        jwt_user = verify_access_token(token)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
        ) from exc

    # Check blocklist
    blocklisted = await db.token_blocklist.find_one({"token_jti": jwt_user.jti})
    if blocklisted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )

    # Fetch full user
    user = await db.users.find_one(document_id_filter(jwt_user.id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


async def require_admin(
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """
    FastAPI dependency: require valid admin JWT.
    Returns admin user document.
    """
    token = get_request_access_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization token",
        )
    try:
        jwt_user = verify_admin_token(token)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid admin token: {exc}",
        ) from exc

    # Check blocklist
    blocklisted = await db.token_blocklist.find_one({"token_jti": jwt_user.jti})
    if blocklisted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )

    user_filter = document_id_filter(jwt_user.id)
    user_filter["role"] = settings.ADMIN_ROLE_NAME
    user = await db.users.find_one(user_filter)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    return user


async def optional_user(request: Request) -> dict[str, Any] | None:
    """
    FastAPI dependency: optionally extract user from JWT.
    Returns None if no valid token.
    """
    token = get_request_access_token(request)
    if not token:
        return None
    try:
        jwt_user = verify_access_token(token)
    except JWTError:
        return None
    return {"_id": jwt_user.id, "email": jwt_user.email, "role": jwt_user.role}
