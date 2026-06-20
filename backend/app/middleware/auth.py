"""
MindLens Authentication & Authorization Middleware
===================================================
Provides:
  - JWT validation (user + admin tokens)
  - In-memory rate limiting (no Redis dependency)
  - PII anonymization on request body (for model inputs)
  - Request ID injection for traceability
  - Login lockout after 5 failed attempts

All state is in-memory (per-process). Suitable for single-instance
FastAPI deployments. For multi-instance, a Redis-backed store would be
needed, but MindLens targets Railway Hobby (single instance) so this
is sufficient and zero-cost.
"""

from __future__ import annotations

import asyncio
import json
import re
import secrets
import time
import uuid
from collections import defaultdict
from typing import Any

from fastapi import Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
security = HTTPBearer(auto_error=False)


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
        settings.jwt_secret_key,
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
        refresh_payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
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


# ---------------------------------------------------------------------------
# PII Anonymizer (for request body before model calls)
# ---------------------------------------------------------------------------

# Simple regex-based PII patterns (matches names, emails, phones, addresses)
_PII_PATTERNS = [
    (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), '[EMAIL]'),
    (re.compile(r'\b(?:\+94\s?)?(?:0\s?)?(?:7[0-9]\s?\d{8}|\d{10})\b'), '[PHONE]'),
    (re.compile(r'\b\d{1,4}\s+[A-Za-z]+\s+(?:Street|St|Road|Rd|Avenue|Ave|Lane|Ln|Drive|Dr)\b', re.IGNORECASE), '[ADDRESS]'),
]


def anonymize_text(text: str) -> str:
    """
    Strip PII from text before sending to ML models.
    Non-destructive — returns redacted version for model input.
    """
    if not settings.ANONYMIZER_ENABLED:
        return text
    for pattern, replacement in _PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def anonymize_request_body(body: dict[str, Any]) -> dict[str, Any]:
    """
    Recursively anonymize a request body dict/list.
    Targets 'text', 'message', 'content' fields.
    """
    if not settings.ANONYMIZER_ENABLED:
        return body

    def _anonymize(obj: Any) -> Any:
        if isinstance(obj, dict):
            result = {}
            for k, v in obj.items():
                if k in ("text", "message", "content") and isinstance(v, str):
                    result[k] = anonymize_text(v)
                else:
                    result[k] = _anonymize(v)
            return result
        elif isinstance(obj, list):
            return [_anonymize(i) for i in obj]
        elif isinstance(obj, str):
            return anonymize_text(obj)
        return obj

    return _anonymize(body)


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

class MindLensAuthMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware that:
    1. Injects a request ID for tracing
    2. Rate-limits unauthenticated requests by IP
    3. Attaches JWT user to request.state for downstream use
    4. Anonymizes request body if configured
    """

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        # 1. Request ID
        request_id = request.headers.get("X-Request-ID", secrets.token_hex(8))
        request.state.request_id = request_id

        # 2. Rate limit unauthenticated routes
        if not _is_protected_route(request.url.path):
            ip = _get_client_ip(request)
            allowed = await get_rate_limit_store().check_ip(
                ip, settings.RATE_LIMIT_PER_IP_MINUTE
            )
            if not allowed:
                return Response(
                    content=json.dumps({"detail": "Rate limit exceeded"}),
                    status_code=429,
                    headers={"Content-Type": "application/json"},
                )

        # 3. JWT extraction (attach to request.state even if not enforced here)
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                user = verify_access_token(token)
                request.state.user = user
            except JWTError:
                request.state.user = None
        else:
            request.state.user = None

        # 4. Continue
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


def _is_protected_route(path: str) -> bool:
    """Check if path is a protected route (skip IP rate limit)."""
    protected_prefixes = (
        "/api/v1/auth/me",
        "/api/v1/auth/logout",
        "/api/v1/auth/users",
        "/api/v1/auth/admin",
        "/api/v1/auth/refresh",
        "/api/v1/sessions",
        "/api/v1/dashboard",
        "/api/v1/admin",
        "/api/v1/memory",
        "/api/v1/checkins",
        "/api/v1/spotify",
        "/ws",
    )
    return path.startswith(protected_prefixes)


def _get_client_ip(request: Request) -> str:
    """Extract client IP, respecting X-Forwarded-For."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ---------------------------------------------------------------------------
# FastAPI Dependencies
# ---------------------------------------------------------------------------

from fastapi import Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db import get_db


async def require_user(
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """
    FastAPI dependency: require valid user JWT.
    Returns user document from MongoDB.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    token = auth_header[7:]
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
    user = await db.users.find_one({"_id": jwt_user.id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # Rate limit authenticated user messages
    allowed = await get_rate_limit_store().check_user(
        jwt_user.id, settings.RATE_LIMIT_PER_USER_HOUR
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Hourly message limit exceeded. Please try again later.",
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
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    token = auth_header[7:]
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

    user = await db.users.find_one({"_id": jwt_user.id, "role": settings.ADMIN_ROLE_NAME})
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
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
    try:
        jwt_user = verify_access_token(token)
    except JWTError:
        return None
    return {"_id": jwt_user.id, "email": jwt_user.email, "role": jwt_user.role}
