"""Logout route for the authentication API."""

from __future__ import annotations

import datetime
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import PyJWTError as JWTError
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import settings
from app.db import get_db
from app.middleware.auth import require_user
from app.routers.auth_helpers import _clear_auth_cookies

router = APIRouter()
security = HTTPBearer(auto_error=False)
@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Logout user",
)
async def logout(
    request: Request,
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Logout endpoint.

    - Adds both access and refresh tokens to blocklist
    - Clears refresh token cookie
    - Invalidates all tokens for this user (security event)
    """
    now = datetime.datetime.now(datetime.UTC)

    # Blocklist access token
    if credentials:
        token = credentials.credentials
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
            )
            jti = payload.get("jti")
            exp = payload.get("exp")
            if jti:
                await db.token_blocklist.insert_one({
                    "token_jti": jti,
                    "expires_at": datetime.datetime.fromtimestamp(exp, datetime.UTC),
                    "created_at": now,
                })
        except JWTError:
            pass  # Already invalid

    # Blocklist refresh token
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        try:
            payload = jwt.decode(
                refresh_token,
                settings.jwt_refresh_secret_key,
                algorithms=[settings.jwt_algorithm],
            )
            jti = payload.get("jti")
            exp = payload.get("exp")
            if jti:
                await db.token_blocklist.insert_one({
                    "token_jti": jti,
                    "expires_at": datetime.datetime.fromtimestamp(exp, datetime.UTC),
                    "created_at": now,
                })
        except JWTError:
            pass

    _clear_auth_cookies(response)

    return {"message": "Logged out successfully"}

