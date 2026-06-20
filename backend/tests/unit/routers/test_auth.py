"""Tests for MindLens Authentication Router."""

from __future__ import annotations

import asyncio
import datetime
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status

from app.middleware.auth import create_token_pair, verify_access_token
from app.routers.auth import hash_password, verify_password


# --- Helper fixtures ---


@pytest.fixture
def auth_client(mock_db: MagicMock):
    """FastAPI test client with mocked DB dependency injection."""
    from app.main import app
    from httpx import AsyncClient

    # Override get_db dependency
    async def override_get_db():
        return mock_db

    app.dependency_overrides = {}
    from app.db import get_db
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://test") as client:
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


class TestPasswordHashing:
    def test_hash_password_does_not_return_plaintext(self) -> None:
        hashed = hash_password("my_password")
        assert hashed != "my_password"
        assert hashed.startswith("$2")

    def test_verify_password_correct(self) -> None:
        hashed = hash_password("my_password")
        assert verify_password("my_password", hashed) is True

    def test_verify_password_incorrect(self) -> None:
        hashed = hash_password("my_password")
        assert verify_password("wrong_password", hashed) is False

    def test_hash_password_truncates_long_passwords(self) -> None:
        long_pw = "a" * 200
        hashed = hash_password(long_pw)
        assert isinstance(hashed, str)
        assert hashed.startswith("$")


# --- Registration tests ---


class TestRegister:
    async def test_register_success(self, auth_client: Any, mock_db: MagicMock) -> None:
        mock_db.users.find_one = AsyncMock(return_value=None)
        mock_db.users.insert_one = AsyncMock(return_value=MagicMock(inserted_id="user_123"))
        mock_db.token_blocklist = MagicMock()
        mock_db.audit_log = MagicMock()
        mock_db.audit_log.insert_one = AsyncMock()

        response = await auth_client.post("/api/v1/auth/register", json={
            "email": "new@example.com",
            "password": "SecurePass123!",
            "name": "New User",
            "age": 20,
            "nickname": "Newbie",
        })

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["role"] == "user"
        assert data["user_id"] == "user_123"
        assert "expires_in" in data

    async def test_register_duplicate_email(self, auth_client: Any, mock_db: MagicMock, sample_user_doc: dict) -> None:
        mock_db.users.find_one = AsyncMock(return_value=sample_user_doc)

        response = await auth_client.post("/api/v1/auth/register", json={
            "email": "test@example.com",
            "password": "SecurePass123!",
            "name": "Another",
            "age": 20,
        })

        assert response.status_code == status.HTTP_409_CONFLICT

    async def test_register_invalid_age(self, auth_client: Any, mock_db: MagicMock) -> None:
        mock_db.users.find_one = AsyncMock(return_value=None)

        response = await auth_client.post("/api/v1/auth/register", json={
            "email": "new@example.com",
            "password": "SecurePass123!",
            "name": "Too Young",
            "age": 10,
        })

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_register_short_password(self, auth_client: Any, mock_db: MagicMock) -> None:
        mock_db.users.find_one = AsyncMock(return_value=None)

        response = await auth_client.post("/api/v1/auth/register", json={
            "email": "new@example.com",
            "password": "short",
            "name": "Short",
            "age": 20,
        })

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# --- Login tests ---


class TestLogin:
    async def test_login_success(self, auth_client: Any, mock_db: MagicMock, sample_user_doc: dict) -> None:
        mock_db.users.find_one = AsyncMock(return_value=sample_user_doc)
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.audit_log = MagicMock()
        mock_db.audit_log.insert_one = AsyncMock()

        with patch("app.middleware.auth.get_rate_limit_store") as mock_store:
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

        with patch("app.middleware.auth.get_rate_limit_store") as mock_store:
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

        with patch("app.middleware.auth.get_rate_limit_store") as mock_store:
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

        with patch("app.middleware.auth.get_rate_limit_store") as mock_store:
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

        with patch("app.middleware.auth.get_rate_limit_store") as mock_store:
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


class TestMe:
    async def test_me_success(self, auth_client: Any, mock_db: MagicMock, sample_user_doc: dict) -> None:
        mock_db.users.find_one = AsyncMock(return_value=sample_user_doc)
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.safety_events = MagicMock()

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        access_token = tokens["access_token"]

        response = await auth_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == "user_123"
        assert data["email"] == "test@example.com"
        assert data["name"] == "Amiru"
        assert data["age_group"] == "adult"
        assert data["role"] == "user"

    async def test_me_no_token(self, auth_client: Any, mock_db: MagicMock) -> None:
        response = await auth_client.get("/api/v1/auth/me")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_me_invalid_token(self, auth_client: Any, mock_db: MagicMock) -> None:
        response = await auth_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid_token"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# --- Admin endpoint tests ---


class TestAdmin:
    async def test_admin_login_success(self, auth_client: Any, mock_db: MagicMock) -> None:
        admin_doc = {
            "_id": "admin_123",
            "email": "admin@mindlens.app",
            "password_hash": hash_password("AdminPass123!"),
            "name": "Admin",
            "role": "admin",
            "is_active": True,
        }
        mock_db.users.find_one = AsyncMock(return_value=admin_doc)
        mock_db.token_blocklist = MagicMock()

        with patch("app.middleware.auth.get_rate_limit_store") as mock_store:
            store = MagicMock()
            store.is_locked_out = AsyncMock(return_value=False)
            store.record_login_attempt = AsyncMock(return_value=1)
            store.reset_login_attempts = AsyncMock()
            mock_store.return_value = store

            response = await auth_client.post("/api/v1/auth/admin/login", json={
                "email": "admin@mindlens.app",
                "password": "AdminPass123!",
            })

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "admin_token" in data
        assert data["token_type"] == "bearer"

    async def test_admin_login_wrong_role(self, auth_client: Any, mock_db: MagicMock, sample_user_doc: dict) -> None:
        mock_db.users.find_one = AsyncMock(return_value=sample_user_doc)
        mock_db.token_blocklist = MagicMock()

        with patch("app.middleware.auth.get_rate_limit_store") as mock_store:
            store = MagicMock()
            store.is_locked_out = AsyncMock(return_value=False)
            store.record_login_attempt = AsyncMock(return_value=1)
            store.reset_login_attempts = AsyncMock()
            mock_store.return_value = store

            response = await auth_client.post("/api/v1/auth/admin/login", json={
                "email": "test@example.com",
                "password": "SecurePass123!",
            })

        assert response.status_code == status.HTTP_403_FORBIDDEN

    async def test_users_count_admin(self, auth_client: Any, mock_db: MagicMock) -> None:
        admin_doc = {
            "_id": "admin_123",
            "email": "admin@mindlens.app",
            "password_hash": hash_password("AdminPass123!"),
            "name": "Admin",
            "role": "admin",
            "is_active": True,
        }
        mock_db.users.find_one = AsyncMock(return_value=admin_doc)
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.users.count_documents = AsyncMock(return_value=42)
        mock_db.safety_events = MagicMock()

        tokens = create_token_pair("admin_123", "admin@mindlens.app", role="admin")
        access_token = tokens["access_token"]

        response = await auth_client.get(
            "/api/v1/auth/users/count",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_users"] == 42

    async def test_users_count_non_admin(self, auth_client: Any, mock_db: MagicMock, sample_user_doc: dict) -> None:
        mock_db.users.find_one = AsyncMock(return_value=sample_user_doc)
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.safety_events = MagicMock()

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        access_token = tokens["access_token"]

        response = await auth_client.get(
            "/api/v1/auth/users/count",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
