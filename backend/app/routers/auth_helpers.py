"""Password and browser-cookie helpers used by the authentication router."""

import datetime
import hashlib
import hmac
import secrets

import bcrypt
from fastapi import Response
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import settings


def hash_password(password: str) -> str:
    """Hash a plain password using bcrypt without silent truncation."""
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > 72:
        raise ValueError("Password must not exceed 72 UTF-8 bytes")
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )
    except (TypeError, ValueError):
        return False


def _audit_ip_hash(ip_address: str) -> str:
    """Create a stable, non-reversible identifier for login audit correlation."""
    return hmac.new(
        settings.jwt_secret_key.encode("utf-8"),
        ip_address.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _set_auth_cookies(response: Response, token_pair: dict[str, str]) -> str:
    """Set secure authentication cookies and return the CSRF token."""
    cookie_options = {
        "httponly": True,
        "secure": settings.effective_cookie_secure,
        "samesite": settings.effective_cookie_samesite,
        "domain": settings.cookie_domain,
    }
    response.set_cookie(
        key="access_token",
        value=token_pair["access_token"],
        max_age=settings.jwt_expire_minutes * 60,
        path="/",
        **cookie_options,
    )
    response.set_cookie(
        key="refresh_token",
        value=token_pair["refresh_token"],
        max_age=settings.jwt_refresh_expire_minutes * 60,
        path="/api/v1/auth",
        **cookie_options,
    )
    csrf_token = secrets.token_urlsafe(32)
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        secure=settings.effective_cookie_secure,
        samesite=settings.effective_cookie_samesite,
        domain=settings.cookie_domain,
        max_age=settings.jwt_refresh_expire_minutes * 60,
        path="/",
    )
    return csrf_token


def _clear_auth_cookies(response: Response) -> None:
    """Expire all browser authentication state."""
    common = {
        "secure": settings.effective_cookie_secure,
        "samesite": settings.effective_cookie_samesite,
        "domain": settings.cookie_domain,
    }
    response.delete_cookie("access_token", path="/", httponly=True, **common)
    response.delete_cookie(
        "refresh_token", path="/api/v1/auth", httponly=True, **common
    )
    response.delete_cookie("csrf_token", path="/", httponly=False, **common)


def utc_from_epoch(value: object) -> datetime.datetime | None:
    """Read a JWT `exp` claim as an aware datetime, or None if it is absent."""
    if not isinstance(value, (int, float)):
        return None
    return datetime.datetime.fromtimestamp(value, datetime.UTC)


async def blocklist_token(
    db: AsyncIOMotorDatabase,
    jti: str,
    expires_at: datetime.datetime | None = None,
    user_id: str | None = None,
) -> None:
    """Revoke one token id, idempotently.

    `token_jti` carries a unique index, so a plain insert turns a second
    logout with the same token — a double click, or a retry after a failed
    cookie clear — into a 500 raised *before* the cookies are cleared, which
    leaves the browser signed in and the client retrying into the same error.

    `expires_at` is the field the TTL index reads, so a row written without
    one outlives the token it revokes and is never reaped. Falling back to the
    longest token life is deliberate: guessing short would let a still-valid
    token come back after its revocation row expired.
    """
    now = datetime.datetime.now(datetime.UTC)
    if expires_at is None:
        expires_at = now + datetime.timedelta(
            minutes=settings.jwt_refresh_expire_minutes
        )
    await db.token_blocklist.update_one(
        {"token_jti": jti},
        {
            "$set": {
                "token_jti": jti,
                "user_id": user_id,
                "expires_at": expires_at,
                "revoked_at": now,
            }
        },
        upsert=True,
    )

