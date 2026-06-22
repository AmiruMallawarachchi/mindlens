"""Tests for MindLens Onboarding Router."""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.middleware.auth import create_token_pair
from fastapi import status


@pytest.fixture
def onboarding_client(mock_db: MagicMock):
    from app.main import app
    from httpx import AsyncClient

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
    return {
        "_id": "user_123",
        "email": "test@example.com",
        "name": None,
        "nickname": None,
        "age": None,
        "age_group": None,
        "role": "user",
        "is_active": True,
        "onboarding_complete": False,
        "created_at": datetime.datetime.now(datetime.UTC),
    }


class TestGetOnboardingStatus:
    async def test_status_step_1(self, onboarding_client: Any, mock_db: MagicMock, sample_user_doc: dict) -> None:
        mock_db.users.find_one = AsyncMock(return_value=sample_user_doc)
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.safety_events = MagicMock()

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        access_token = tokens["access_token"]

        response = await onboarding_client.get(
            "/api/v1/onboarding/status",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["onboarding_complete"] is False
        assert data["current_step"] == 1

    async def test_status_step_5(self, onboarding_client: Any, mock_db: MagicMock, sample_user_doc: dict) -> None:
        doc = dict(sample_user_doc)
        doc["name"] = "Amiru"
        doc["nickname"] = "Ami"
        doc["age"] = 22
        doc["age_group"] = "adult"
        doc["onboarding_people"] = [{"name": "Ravi", "role": "best friend"}]
        doc["checkin_preferred_time"] = "evening"
        mock_db.users.find_one = AsyncMock(return_value=doc)
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.safety_events = MagicMock()

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        access_token = tokens["access_token"]

        response = await onboarding_client.get(
            "/api/v1/onboarding/status",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["current_step"] == 5

    async def test_status_onboarding_complete(self, onboarding_client: Any, mock_db: MagicMock, sample_user_doc: dict) -> None:
        doc = dict(sample_user_doc)
        doc["onboarding_complete"] = True
        doc["name"] = "Amiru"
        doc["age"] = 22
        mock_db.users.find_one = AsyncMock(return_value=doc)
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.safety_events = MagicMock()

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        access_token = tokens["access_token"]

        response = await onboarding_client.get(
            "/api/v1/onboarding/status",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["onboarding_complete"] is True
        assert data["current_step"] == 6


class TestSubmitOnboardingStep:
    async def test_step_1_name(self, onboarding_client: Any, mock_db: MagicMock, sample_user_doc: dict) -> None:
        mock_db.users.find_one = AsyncMock(return_value=sample_user_doc)
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.users.update_one = AsyncMock()
        mock_db.safety_events = MagicMock()

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        access_token = tokens["access_token"]

        response = await onboarding_client.post(
            "/api/v1/onboarding/step/1",
            json={"name": "Amiru"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["step"] == 1
        assert data["next_step"] == 2

    async def test_step_3_age(self, onboarding_client: Any, mock_db: MagicMock, sample_user_doc: dict) -> None:
        doc = dict(sample_user_doc)
        doc["name"] = "Amiru"
        doc["nickname"] = "Ami"
        mock_db.users.find_one = AsyncMock(return_value=doc)
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.users.update_one = AsyncMock()
        mock_db.safety_events = MagicMock()

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        access_token = tokens["access_token"]

        response = await onboarding_client.post(
            "/api/v1/onboarding/step/3",
            json={"age": 22},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["step"] == 3
        assert data["next_step"] == 4

    async def test_step_5_complete(self, onboarding_client: Any, mock_db: MagicMock, sample_user_doc: dict) -> None:
        doc = dict(sample_user_doc)
        doc["name"] = "Amiru"
        doc["nickname"] = "Ami"
        doc["age"] = 22
        doc["age_group"] = "adult"
        doc["onboarding_people"] = [{"name": "Ravi", "role": "best friend"}]
        mock_db.users.find_one = AsyncMock(return_value=doc)
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.users.update_one = AsyncMock()
        mock_db.user_memory = MagicMock()
        mock_db.user_memory.update_one = AsyncMock()
        mock_db.safety_events = MagicMock()
        mock_db.sessions = MagicMock()
        mock_db.sessions.insert_one = AsyncMock()

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        access_token = tokens["access_token"]

        response = await onboarding_client.post(
            "/api/v1/onboarding/step/5",
            json={"checkin_preferred_time": "evening"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["onboarding_complete"] is True

    async def test_invalid_step(self, onboarding_client: Any, mock_db: MagicMock, sample_user_doc: dict) -> None:
        mock_db.users.find_one = AsyncMock(return_value=sample_user_doc)
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.safety_events = MagicMock()

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        access_token = tokens["access_token"]

        response = await onboarding_client.post(
            "/api/v1/onboarding/step/99",
            json={"name": "test"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestCompleteOnboarding:
    async def test_complete_onboarding(self, onboarding_client: Any, mock_db: MagicMock, sample_user_doc: dict) -> None:
        mock_db.users.find_one = AsyncMock(return_value=sample_user_doc)
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.users.update_one = AsyncMock()
        mock_db.user_memory = MagicMock()
        mock_db.user_memory.update_one = AsyncMock()
        mock_db.safety_events = MagicMock()
        mock_db.sessions = MagicMock()
        mock_db.sessions.insert_one = AsyncMock()

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        access_token = tokens["access_token"]

        response = await onboarding_client.post(
            "/api/v1/onboarding/complete",
            json={
                "name": "Amiru",
                "nickname": "Ami",
                "age": 22,
                "people": [{"name": "Ravi", "role": "best friend"}],
                "checkin_preferred_time": "evening",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["onboarding_complete"] is True
        assert data["session_id"] is not None
        assert "access_token" in data
