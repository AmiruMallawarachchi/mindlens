"""Tests for MindLens Authentication & Authorization Middleware."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

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
from jose import JWTError, jwt

# --- Token creation / verification tests ---


class TestTokenCreation:
    def test_create_token_pair_returns_both_tokens(self) -> None:
        result = create_token_pair("user_123", "test@example.com", role="user")
        assert "access_token" in result
        assert "refresh_token" in result
        assert "jti" in result
        assert "expires_in" in result

    def test_create_token_pair_has_correct_claims(self) -> None:
        result = create_token_pair("user_123", "test@example.com", role="user")
        access_payload = jwt.decode(
            result["access_token"], settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        assert access_payload["sub"] == "user_123"
        assert access_payload["email"] == "test@example.com"
        assert access_payload["role"] == "user"
        assert access_payload["type"] == "access"

        refresh_payload = jwt.decode(
            result["refresh_token"], settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        assert refresh_payload["type"] == "refresh"
        assert "access_jti" in refresh_payload

    def test_create_admin_token(self) -> None:
        token = create_admin_token("admin_123", "admin@mindlens.app")
        payload = jwt.decode(
            token, settings.admin_jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        assert payload["sub"] == "admin_123"
        assert payload["role"] == "admin"
        assert payload["type"] == "admin"


class TestTokenVerification:
    def test_verify_access_token_success(self) -> None:
        result = create_token_pair("user_123", "test@example.com", role="user")
        user = verify_access_token(result["access_token"])
        assert user.id == "user_123"
        assert user.email == "test@example.com"
        assert user.role == "user"
        assert user.is_admin() is False

    def test_verify_access_token_wrong_type_fails(self) -> None:
        result = create_token_pair("user_123", "test@example.com", role="user")
        with pytest.raises(JWTError):
            verify_access_token(result["refresh_token"])

    def test_verify_refresh_token_success(self) -> None:
        result = create_token_pair("user_123", "test@example.com", role="user")
        user = verify_refresh_token(result["refresh_token"])
        assert user.id == "user_123"

    def test_verify_admin_token_success(self) -> None:
        token = create_admin_token("admin_123", "admin@mindlens.app")
        user = verify_admin_token(token)
        assert user.id == "admin_123"
        assert user.is_admin() is True

    def test_verify_admin_token_with_user_token_fails(self) -> None:
        result = create_token_pair("user_123", "test@example.com", role="user")
        with pytest.raises(JWTError):
            verify_admin_token(result["access_token"])

    def test_verify_expired_token_fails(self) -> None:
        # Create a token that expired 1 second ago
        now = time.time() - 1
        payload = {
            "sub": "user_123",
            "email": "test@example.com",
            "role": "user",
            "type": "access",
            "jti": "test_jti",
            "iat": now - 3600,
            "exp": now,
        }
        token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
        with pytest.raises(JWTError):
            verify_access_token(token)


class TestJWTUser:
    def test_is_admin_true(self) -> None:
        user = JWTUser({"sub": "a", "email": "a@b.com", "role": "admin", "jti": "x"})
        assert user.is_admin() is True

    def test_is_admin_false(self) -> None:
        user = JWTUser({"sub": "a", "email": "a@b.com", "role": "user", "jti": "x"})
        assert user.is_admin() is False

    def test_default_role_user(self) -> None:
        user = JWTUser({"sub": "a", "email": "a@b.com", "jti": "x"})
        assert user.role == "user"


# --- Rate limit tests ---


class TestRateLimitStore:
    @pytest.fixture
    def store(self) -> RateLimitStore:
        return RateLimitStore()

    @pytest.mark.asyncio
    async def test_check_ip_allowed(self, store: RateLimitStore) -> None:
        result = await store.check_ip("127.0.0.1", limit=100)
        assert result is True

    @pytest.mark.asyncio
    async def test_check_ip_exceeded(self, store: RateLimitStore) -> None:
        for _ in range(5):
            await store.check_ip("127.0.0.1", limit=5)
        result = await store.check_ip("127.0.0.1", limit=5)
        assert result is False

    @pytest.mark.asyncio
    async def test_check_ip_window_expires(self, store: RateLimitStore) -> None:
        # Old entries should be cleaned
        for _ in range(5):
            await store.check_ip("127.0.0.1", limit=5, window=0)  # 0-second window
        # All entries are immediately expired
        result = await store.check_ip("127.0.0.1", limit=5, window=0)
        assert result is True

    @pytest.mark.asyncio
    async def test_check_user_allowed(self, store: RateLimitStore) -> None:
        result = await store.check_user("user_123", limit=60)
        assert result is True

    @pytest.mark.asyncio
    async def test_check_user_exceeded(self, store: RateLimitStore) -> None:
        for _ in range(3):
            await store.check_user("user_123", limit=3)
        result = await store.check_user("user_123", limit=3)
        assert result is False

    @pytest.mark.asyncio
    async def test_login_lockout(self, store: RateLimitStore) -> None:
        # Simulate 5 failed attempts
        for _ in range(5):
            await store.record_login_attempt("email@test.com")

        locked = await store.is_locked_out("email@test.com", max_attempts=5)
        assert locked is True

    @pytest.mark.asyncio
    async def test_login_lockout_below_threshold(self, store: RateLimitStore) -> None:
        for _ in range(4):
            await store.record_login_attempt("email@test.com")

        locked = await store.is_locked_out("email@test.com", max_attempts=5)
        assert locked is False

    @pytest.mark.asyncio
    async def test_reset_login_attempts(self, store: RateLimitStore) -> None:
        for _ in range(5):
            await store.record_login_attempt("email@test.com")
        await store.reset_login_attempts("email@test.com")
        locked = await store.is_locked_out("email@test.com", max_attempts=5)
        assert locked is False

    @pytest.mark.asyncio
    async def test_is_locked_out_expires(self, store: RateLimitStore) -> None:
        # Old attempts should expire after 15 min (900s)
        # We simulate by adding an attempt with a very old timestamp
        store._login_attempts["old@test.com"] = [time.time() - 1000]
        locked = await store.is_locked_out("old@test.com", max_attempts=1)
        assert locked is False


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
