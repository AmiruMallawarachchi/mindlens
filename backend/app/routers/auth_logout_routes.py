"""Logout route for the authentication API."""

from __future__ import annotations

from typing import Any

import jwt
from fastapi import APIRouter, Depends, Request, Response, status
from jwt.exceptions import PyJWTError as JWTError
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import settings
from app.db import get_db
from app.middleware.auth_tokens import get_request_access_token
from app.routers.auth_helpers import _clear_auth_cookies, blocklist_token, utc_from_epoch
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


def _claims(token: str, secret: str, expected_type: str) -> dict[str, Any] | None:
    """Decode a token for revocation, or return None if it cannot be trusted.

    A token that no longer verifies needs no revocation: an expired one is
    already useless and a forged one was never accepted in the first place.
    """
    try:
        payload = jwt.decode(token, secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
    if payload.get("type") != expected_type:
        return None
    return payload


@router.post("/logout", status_code=status.HTTP_200_OK, summary="Logout user")
async def logout(
    request: Request,
    response: Response,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Revoke the tokens this browser is holding, then clear the auth cookies.

    The access token is read from the bearer header *or* the cookie, because
    clients use both paths and the old header-only version left a
    cookie-authenticated logout revoking nothing at all. The refresh token's
    `access_jti` is revoked too — after a silent refresh that is the live
    access token, and the one in the header may already be superseded.

    Only this device's pair is revoked; signing out everywhere is Settings >
    Account > Sessions. Revocation is best-effort so a storage failure cannot
    leave the UI stuck: the cookies are cleared either way.
    """
    tokens: list[tuple[str, Any]] = []
    session_jti = None

    access = get_request_access_token(request)
    if access:
        claims = _claims(access, settings.jwt_secret_key, "access")
        if claims and claims.get("jti"):
            tokens.append((claims["jti"], claims))
            session_jti = claims["jti"]

    user_id = None
    refresh = request.cookies.get("refresh_token")
    if refresh:
        claims = _claims(refresh, settings.jwt_refresh_secret_key, "refresh")
        if claims:
            if claims.get("jti"):
                tokens.append((claims["jti"], claims))
            if claims.get("access_jti"):
                tokens.append((claims["access_jti"], claims))
                session_jti = session_jti or claims["access_jti"]
            user_id = claims.get("sub")

    if user_id is None and tokens:
        user_id = tokens[0][1].get("sub")

    for jti, claims in tokens:
        try:
            await blocklist_token(db, jti, utc_from_epoch(claims.get("exp")), user_id)
        except Exception as exc:
            logger.warning("Could not revoke token %s at logout: %s", jti[:8], exc)

    if user_id and session_jti:
        try:
            await db.user_sessions.delete_one({"user_id": user_id, "jti": session_jti})
        except Exception as exc:
            logger.warning("Could not forget the logout session row: %s", exc)

    _clear_auth_cookies(response)

    return {"message": "Logged out successfully"}
