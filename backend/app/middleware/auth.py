"""Authentication middleware and compatibility exports."""

from __future__ import annotations

import hmac
import json
import secrets
from typing import Any

from fastapi import Request, Response, status
from jwt.exceptions import PyJWTError as JWTError
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.middleware.auth_dependencies import optional_user, require_admin, require_user
from app.middleware.auth_pii import anonymize_request_body, anonymize_text
from app.middleware.auth_tokens import (
    JWTUser,
    RateLimitStore,
    create_admin_token,
    create_token_pair,
    get_rate_limit_store,
    get_request_access_token,
    verify_access_token,
    verify_admin_token,
    verify_refresh_token,
)

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

        if self._csrf_failed(request):
            return Response(
                content=json.dumps({"detail": "CSRF validation failed"}),
                status_code=status.HTTP_403_FORBIDDEN,
                headers={"Content-Type": "application/json", "X-Request-ID": request_id},
            )

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
        token = get_request_access_token(request)
        if token:
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

    @staticmethod
    def _csrf_failed(request: Request) -> bool:
        """Protect cookie-authenticated state changes in cross-site production use."""
        if not settings.is_production or request.method in {"GET", "HEAD", "OPTIONS"}:
            return False
        if request.url.path in {"/api/v1/auth/register", "/api/v1/auth/login"}:
            return False
        if not (
            request.cookies.get("access_token") or request.cookies.get("refresh_token")
        ):
            return False
        cookie_token = request.cookies.get("csrf_token", "")
        header_token = request.headers.get("X-CSRF-Token", "")
        return not (
            cookie_token
            and header_token
            and hmac.compare_digest(cookie_token, header_token)
        )


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
        "/ws",
    )
    return path.startswith(protected_prefixes)


def _get_client_ip(request: Request) -> str:
    """Extract client IP, respecting X-Forwarded-For."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
