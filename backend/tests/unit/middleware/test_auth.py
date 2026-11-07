"""Tests for MindLens Authentication & Authorization Middleware."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from app.middleware.auth import MindLensAuthMiddleware, RateLimitStore
from fastapi import Request, Response

# PII scrubbing is tested where it actually happens — tests/unit/core/
# test_anonymizer.py. This middleware never saw request bodies, whatever its
# old docstring said.

# --- Middleware tests ---


class TestMindLensAuthMiddleware:
    @pytest.fixture
    def middleware(self) -> MindLensAuthMiddleware:
        return MindLensAuthMiddleware(app=MagicMock())

    @pytest.mark.asyncio
    async def test_injects_request_id(self, middleware: MindLensAuthMiddleware) -> None:
        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/test"
        request.method = "GET"
        request.headers = {}
        request.client = MagicMock(host="127.0.0.1")
        request.state = MagicMock()

        async def next_call(req: Request) -> Response:
            return Response(content="ok", status_code=200)

        response = await middleware.dispatch(request, next_call)
        assert response.headers["X-Request-ID"] is not None

    @pytest.mark.asyncio
    async def test_rate_limits_unauthenticated(self, middleware: MindLensAuthMiddleware) -> None:
        request = MagicMock(spec=Request)
        request.url.path = "/health"
        request.method = "GET"
        request.headers = {}
        request.client = MagicMock(host="127.0.0.1")
        request.state = MagicMock()

        with patch("app.middleware.auth.get_rate_limit_store") as mock_store:
            store = RateLimitStore()
            # Exceed the limit by making many requests
            for _ in range(101):
                await store.check_ip("127.0.0.1", limit=100)
            mock_store.return_value = store

            async def next_call(req: Request) -> Response:
                return Response(content="ok", status_code=200)

            response = await middleware.dispatch(request, next_call)
            assert response.status_code == 429
