"""Tests for MindLens Authentication Router."""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.middleware.auth import create_token_pair
from app.routers.auth import hash_password
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

        with patch("app.routers.auth_admin_routes.get_rate_limit_store") as mock_store:
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

        with patch("app.routers.auth_admin_routes.get_rate_limit_store") as mock_store:
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
