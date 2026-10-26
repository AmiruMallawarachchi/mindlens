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

    def test_hash_password_rejects_long_passwords(self) -> None:
        long_pw = "a" * 200
        with pytest.raises(ValueError, match="72 UTF-8 bytes"):
            hash_password(long_pw)


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


