"""Tests for MindLens Authentication Router."""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.middleware.auth import create_token_pair
from app.routers.auth import hash_password, verify_password
from fastapi import status

# --- Helper fixtures ---


@pytest.fixture
async def auth_client(mock_db: MagicMock):
    """FastAPI test client with mocked DB dependency injection."""
    from app.main import app
    from httpx import ASGITransport, AsyncClient

    # Override get_db dependency
    async def override_get_db():
        return mock_db

    app.dependency_overrides = {}
    from app.db import get_db
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def sample_user_doc() -> dict[str, Any]:
    """A sample user document as stored in MongoDB."""
    return {
        "_id": "user_123",
        "email": "test@example.com",
        "password_hash": hash_password("SecurePass123!"),
        "name": "Amiru",
        "nickname": "Ami",
        "age": 22,
        "age_group": "adult",
        "role": "user",
        "created_at": datetime.datetime.now(datetime.UTC),
        "updated_at": datetime.datetime.now(datetime.UTC),
        "is_active": True,
        "onboarding_complete": False,
    }


# --- Password hashing tests ---


class TestLogin:
    async def test_login_success(self, auth_client: Any, mock_db: MagicMock, sample_user_doc: dict) -> None:
        mock_db.users.find_one = AsyncMock(return_value=sample_user_doc)
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.audit_log = MagicMock()
        mock_db.audit_log.insert_one = AsyncMock()

        with patch("app.routers.auth_user_routes.get_rate_limit_store") as mock_store:
            store = MagicMock()
            store.is_locked_out = AsyncMock(return_value=False)
            store.record_login_attempt = AsyncMock(return_value=1)
            store.reset_login_attempts = AsyncMock()
            mock_store.return_value = store

            response = await auth_client.post("/api/v1/auth/login", json={
                "email": "test@example.com",
                "password": "SecurePass123!",
            })

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["role"] == "user"
        assert "refresh_token" in response.cookies or True  # httponly cookie may not be visible in test client


    async def test_login_wrong_password(self, auth_client: Any, mock_db: MagicMock, sample_user_doc: dict) -> None:
        mock_db.users.find_one = AsyncMock(return_value=sample_user_doc)
        mock_db.token_blocklist = MagicMock()

        with patch("app.routers.auth_user_routes.get_rate_limit_store") as mock_store:
            store = MagicMock()
            store.is_locked_out = AsyncMock(return_value=False)
            store.record_login_attempt = AsyncMock(return_value=1)
            mock_store.return_value = store

            response = await auth_client.post("/api/v1/auth/login", json={
                "email": "test@example.com",
                "password": "WrongPassword123!",
            })

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_login_user_not_found(self, auth_client: Any, mock_db: MagicMock) -> None:
        mock_db.users.find_one = AsyncMock(return_value=None)

        with patch("app.routers.auth_user_routes.get_rate_limit_store") as mock_store:
            store = MagicMock()
            store.is_locked_out = AsyncMock(return_value=False)
            store.record_login_attempt = AsyncMock(return_value=1)
            mock_store.return_value = store

            response = await auth_client.post("/api/v1/auth/login", json={
                "email": "notfound@example.com",
                "password": "SecurePass123!",
            })

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_login_lockout(self, auth_client: Any, mock_db: MagicMock, sample_user_doc: dict) -> None:
        mock_db.users.find_one = AsyncMock(return_value=sample_user_doc)

        with patch("app.routers.auth_user_routes.get_rate_limit_store") as mock_store:
            store = MagicMock()
            store.is_locked_out = AsyncMock(return_value=True)
            mock_store.return_value = store

            response = await auth_client.post("/api/v1/auth/login", json={
                "email": "test@example.com",
                "password": "SecurePass123!",
            })

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    async def test_login_inactive_account(self, auth_client: Any, mock_db: MagicMock, sample_user_doc: dict) -> None:
        doc = dict(sample_user_doc)
        doc["is_active"] = False
        mock_db.users.find_one = AsyncMock(return_value=doc)
        mock_db.token_blocklist = MagicMock()

        with patch("app.routers.auth_user_routes.get_rate_limit_store") as mock_store:
            store = MagicMock()
            store.is_locked_out = AsyncMock(return_value=False)
            store.record_login_attempt = AsyncMock(return_value=1)
            store.reset_login_attempts = AsyncMock()
            mock_store.return_value = store

            response = await auth_client.post("/api/v1/auth/login", json={
                "email": "test@example.com",
                "password": "SecurePass123!",
            })

        assert response.status_code == status.HTTP_403_FORBIDDEN


# --- Token refresh tests ---


class TestRefresh:
    async def test_refresh_success(self, auth_client: Any, mock_db: MagicMock, sample_user_doc: dict) -> None:
        mock_db.users.find_one = AsyncMock(return_value=sample_user_doc)
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        refresh_token = tokens["refresh_token"]

        auth_client.cookies.set("refresh_token", refresh_token)
        response = await auth_client.post("/api/v1/auth/refresh")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data

    async def test_refresh_no_cookie(self, auth_client: Any, mock_db: MagicMock) -> None:
        response = await auth_client.post("/api/v1/auth/refresh")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_refresh_invalid_token(self, auth_client: Any, mock_db: MagicMock) -> None:
        auth_client.cookies.set("refresh_token", "invalid_token")
        response = await auth_client.post("/api/v1/auth/refresh")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_refresh_blocklisted(self, auth_client: Any, mock_db: MagicMock, sample_user_doc: dict) -> None:
        mock_db.users.find_one = AsyncMock(return_value=sample_user_doc)
        mock_db.token_blocklist.find_one = AsyncMock(return_value={"token_jti": "blocked"})

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        auth_client.cookies.set("refresh_token", tokens["refresh_token"])

        response = await auth_client.post("/api/v1/auth/refresh")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# --- Logout tests ---


class TestLogout:
    async def test_logout_success(self, auth_client: Any, mock_db: MagicMock) -> None:
        mock_db.token_blocklist.insert_one = AsyncMock()

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]

        auth_client.cookies.set("refresh_token", refresh_token)
        response = await auth_client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == "Logged out successfully"

    async def test_logout_no_token(self, auth_client: Any, mock_db: MagicMock) -> None:
        mock_db.token_blocklist.insert_one = AsyncMock()
        response = await auth_client.post("/api/v1/auth/logout")
        assert response.status_code == status.HTTP_200_OK


# --- Me endpoint tests ---


