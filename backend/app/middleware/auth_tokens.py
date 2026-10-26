"""JWT creation, verification, and process-local rate limiting."""

from __future__ import annotations

import asyncio
import time
import uuid
from collections import defaultdict
from typing import Any

import jwt
from jwt.exceptions import PyJWTError as JWTError

from app.config import settings


# ---------------------------------------------------------------------------
# Rate-Limit Store (in-memory)
# ---------------------------------------------------------------------------

class RateLimitStore:
    """
    Thread-safe (asyncio-aware) in-memory rate limit store.
    """

    def __init__(self) -> None:
        self._ip_minute: dict[str, list[float]] = defaultdict(list)
        self._user_hour: dict[str, list[float]] = defaultdict(list)
        self._login_attempts: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def check_ip(self, ip: str, limit: int, window: int = 60) -> bool:
        """Return True if request is allowed."""
        now = time.time()
        async with self._lock:
            # Clean old entries
            self._ip_minute[ip] = [
                t for t in self._ip_minute[ip] if now - t < window
            ]
            if len(self._ip_minute[ip]) >= limit:
                return False
            self._ip_minute[ip].append(now)
            return True

    async def check_user(self, user_id: str, limit: int, window: int = 3600) -> bool:
        """Return True if user is within their hourly message limit."""
        now = time.time()
        async with self._lock:
            self._user_hour[user_id] = [
                t for t in self._user_hour[user_id] if now - t < window
            ]
            if len(self._user_hour[user_id]) >= limit:
                return False
            self._user_hour[user_id].append(now)
            return True

    async def record_login_attempt(self, identifier: str) -> int:
        """Record a failed login attempt. Returns current count."""
        now = time.time()
        async with self._lock:
            self._login_attempts[identifier] = [
                t for t in self._login_attempts[identifier] if now - t < 900  # 15 min
            ]
            self._login_attempts[identifier].append(now)
            return len(self._login_attempts[identifier])

    async def reset_login_attempts(self, identifier: str) -> None:
        async with self._lock:
            self._login_attempts.pop(identifier, None)

    async def is_locked_out(self, identifier: str, max_attempts: int = 5) -> bool:
        async with self._lock:
            now = time.time()
            attempts = [
                t for t in self._login_attempts.get(identifier, [])
                if now - t < 900
            ]
            return len(attempts) >= max_attempts


# Singleton
_rate_limit_store = RateLimitStore()


def get_rate_limit_store() -> RateLimitStore:
    return _rate_limit_store


# ---------------------------------------------------------------------------
# JWT Helpers
# ---------------------------------------------------------------------------

class JWTUser:
    """Lightweight user object extracted from JWT."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.id: str = payload.get("sub", "")
        self.email: str = payload.get("email", "")
        self.role: str = payload.get("role", settings.USER_ROLE_NAME)
        self.jti: str = payload.get("jti", "")

    def is_admin(self) -> bool:
        return self.role == settings.ADMIN_ROLE_NAME


def verify_access_token(token: str) -> JWTUser:
    """
    Verify a user access token.
    Raises JWTError if invalid or expired.
    """
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    if payload.get("type") != "access":
        raise JWTError("Invalid token type")
    return JWTUser(payload)


def verify_refresh_token(token: str) -> JWTUser:
    """
    Verify a refresh token.
    Raises JWTError if invalid or expired.
    """
    payload = jwt.decode(
        token,
        settings.jwt_refresh_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    if payload.get("type") != "refresh":
        raise JWTError("Invalid token type")
    return JWTUser(payload)


def verify_admin_token(token: str) -> JWTUser:
    """
    Verify an admin token (signed with separate secret).
    Raises JWTError if invalid, expired, or not admin.
    """
    payload = jwt.decode(
        token,
        settings.admin_jwt_secret,
        algorithms=[settings.jwt_algorithm],
    )
    if payload.get("type") != "admin":
        raise JWTError("Invalid token type")
    if payload.get("role") != settings.ADMIN_ROLE_NAME:
        raise JWTError("Insufficient privileges")
    return JWTUser(payload)


def create_token_pair(user_id: str, email: str, role: str = "user") -> dict[str, str]:
    """
    Create an access token + refresh token pair.
    Returns dict with access_token, refresh_token, and metadata.
    """
    now = time.time()
    jti = str(uuid.uuid4())

    access_payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "type": "access",
        "jti": jti,
        "iat": now,
        "exp": now + (settings.jwt_expire_minutes * 60),
    }

    refresh_jti = str(uuid.uuid4())
    refresh_payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "type": "refresh",
        "jti": refresh_jti,
        "access_jti": jti,
        "iat": now,
        "exp": now + (settings.jwt_refresh_expire_minutes * 60),
    }

    access_token = jwt.encode(
        access_payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )
    refresh_token = jwt.encode(
        refresh_payload,
        settings.jwt_refresh_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "jti": jti,
        "refresh_jti": refresh_jti,
        "expires_in": settings.jwt_expire_minutes * 60,
    }


def create_admin_token(user_id: str, email: str) -> str:
    """Create a short-lived admin token."""
    now = time.time()
    payload = {
        "sub": user_id,
        "email": email,
        "role": settings.ADMIN_ROLE_NAME,
        "type": "admin",
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + (settings.admin_jwt_expire_minutes * 60),
    }
    return jwt.encode(
        payload, settings.admin_jwt_secret, algorithm=settings.jwt_algorithm
    )




def get_request_access_token(request: Any) -> str | None:
    """Read an access token from a bearer header or secure cookie."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return request.cookies.get("access_token")
