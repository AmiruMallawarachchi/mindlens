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
            result["refresh_token"],
            settings.jwt_refresh_secret_key,
            algorithms=[settings.jwt_algorithm],
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


