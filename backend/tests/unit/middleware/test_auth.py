"""Tests for MindLens Authentication & Authorization Middleware."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import jwt
import pytest
from app.config import settings
from app.middleware.auth import (
    JWTUser,
    MindLensAuthMiddleware,
    RateLimitStore,
    anonymize_request_body,
    anonymize_text,
    create_admin_token,
    create_token_pair,
    verify_access_token,
    verify_admin_token,
    verify_refresh_token,
)
from fastapi import Request, Response
from jwt.exceptions import PyJWTError as JWTError

# --- Anonymizer tests ---


class TestAnonymizeText:
    def test_anonymize_email(self) -> None:
        text = "Contact me at amiru@example.com please"
        result = anonymize_text(text)
        assert "[EMAIL]" in result
        assert "amiru@example.com" not in result

    def test_anonymize_phone(self) -> None:
        text = "Call me at 0771234567"
        result = anonymize_text(text)
        assert "[PHONE]" in result
        assert "0771234567" not in result

    def test_anonymize_multiple_emails(self) -> None:
        text = "Emails: a@b.com and c@d.com"
        result = anonymize_text(text)
        assert result.count("[EMAIL]") == 2

    def test_anonymize_no_pii(self) -> None:
        text = "I feel anxious today"
        result = anonymize_text(text)
        assert result == "I feel anxious today"

    def test_anonymize_empty_string(self) -> None:
        assert anonymize_text("") == ""


class TestAnonymizeRequestBody:
    def test_anonymize_dict_with_text_field(self) -> None:
        body = {"text": "Email me at test@example.com", "other": "safe"}
        result = anonymize_request_body(body)
        assert "[EMAIL]" in result["text"]
        assert result["other"] == "safe"

    def test_anonymize_dict_with_message_field(self) -> None:
        body = {"message": "Call 0771234567", "type": "user"}
        result = anonymize_request_body(body)
        assert "[PHONE]" in result["message"]
        assert result["type"] == "user"

    def test_anonymize_nested_dict(self) -> None:
        body = {"payload": {"text": "Email at a@b.com"}}
        result = anonymize_request_body(body)
        assert "[EMAIL]" in result["payload"]["text"]

    def test_anonymize_list_in_dict(self) -> None:
        body = {"messages": [{"text": "a@b.com"}, {"text": "hello"}]}
        result = anonymize_request_body(body)
        assert "[EMAIL]" in result["messages"][0]["text"]
        assert result["messages"][1]["text"] == "hello"

    def test_anonymize_no_text_fields(self) -> None:
        body = {"count": 5, "active": True}
        result = anonymize_request_body(body)
        assert result == body


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
