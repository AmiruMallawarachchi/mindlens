"""Tests for MindLens Memory Router."""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.middleware.auth import create_token_pair
from fastapi import status


@pytest.fixture
async def memory_client(mock_db: MagicMock):
    from app.main import app
    from httpx import ASGITransport, AsyncClient

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
def sample_memory_doc() -> dict[str, Any]:
    return {
        "_id": "mem_123",
        "user_id": "user_123",
        "display_name": "Amiru's Memory",
        "profile": {
            "name": "Amiru",
            "nickname": "Ami",
            "age": 22,
            "age_group": "adult",
            "onboarding_complete": True,
        },
        "people": {
            "Ravi": {"role": "best friend", "context": "also doing same exam", "sentiment": "positive"},
        },
        "emotional_patterns": {
            "most_common_emotion": "anxiety",
            "average_distress": 0.6,
            "trigger_topics": ["exams", "sleep"],
            "effective_coping": ["breathing", "music"],
        },
        "preferences": {
            "music_genres": ["lofi", "classical"],
            "mindfulness_style": "box breathing",
            "introvert_score": 0.7,
            "preferred_modality": "CBT",
            "checkin_preferred_time": "evening",
        },
        "milestones": ["Completed onboarding"],
        "raw_notes": [],
        "created_at": datetime.datetime.now(datetime.UTC),
        "updated_at": datetime.datetime.now(datetime.UTC),
    }


class TestGetMemory:
    async def test_get_memory_success(self, memory_client: Any, mock_db: MagicMock, sample_memory_doc: dict) -> None:
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.user_memory.find_one = AsyncMock(return_value=sample_memory_doc)
        mock_db.safety_events = MagicMock()

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        access_token = tokens["access_token"]

        response = await memory_client.get(
            "/api/v1/memory",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["user_id"] == "user_123"
        assert data["display_name"] == "Amiru's Memory"
        assert data["profile"]["name"] == "Amiru"

    async def test_get_memory_not_found(self, memory_client: Any, mock_db: MagicMock) -> None:
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.user_memory.find_one = AsyncMock(return_value=None)
        mock_db.safety_events = MagicMock()

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        access_token = tokens["access_token"]

        response = await memory_client.get(
            "/api/v1/memory",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestUpdatePeople:
    async def test_update_people(self, memory_client: Any, mock_db: MagicMock, sample_memory_doc: dict) -> None:
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.user_memory.update_one = AsyncMock(return_value=MagicMock(matched_count=1))
        mock_db.safety_events = MagicMock()

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        access_token = tokens["access_token"]

        response = await memory_client.patch(
            "/api/v1/memory/people",
            json={
                "people": {
                    "Ravi": {"role": "best friend", "context": "same exam", "sentiment": "positive"},
                    "mum": {"role": "mother", "context": "worried", "sentiment": "mixed"},
                }
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 2


class TestUpdatePreferences:
    async def test_update_preferences(self, memory_client: Any, mock_db: MagicMock, sample_memory_doc: dict) -> None:
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.user_memory.update_one = AsyncMock(return_value=MagicMock(matched_count=1))
        mock_db.safety_events = MagicMock()

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        access_token = tokens["access_token"]

        response = await memory_client.patch(
            "/api/v1/memory/preferences",
            json={
                "mindfulness_style": "4-7-8 breathing",
                "introvert_score": 0.8,
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_200_OK

    async def test_update_preferences_empty(self, memory_client: Any, mock_db: MagicMock, sample_memory_doc: dict) -> None:
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.safety_events = MagicMock()

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        access_token = tokens["access_token"]

        response = await memory_client.patch(
            "/api/v1/memory/preferences",
            json={},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestAddNote:
    async def test_add_note(self, memory_client: Any, mock_db: MagicMock, sample_memory_doc: dict) -> None:
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.user_memory.update_one = AsyncMock(return_value=MagicMock(matched_count=1))
        mock_db.safety_events = MagicMock()

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        access_token = tokens["access_token"]

        response = await memory_client.post(
            "/api/v1/memory/notes",
            json={"text": "I noticed I feel better after morning walks."},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "note_id" in data


class TestDeleteNote:
    async def test_delete_note(self, memory_client: Any, mock_db: MagicMock, sample_memory_doc: dict) -> None:
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.user_memory.update_one = AsyncMock()
        mock_db.safety_events = MagicMock()

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        access_token = tokens["access_token"]

        response = await memory_client.delete(
            "/api/v1/memory/notes/abc123",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_200_OK


class TestDeleteEntry:
    async def test_delete_person(self, memory_client: Any, mock_db: MagicMock, sample_memory_doc: dict) -> None:
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.user_memory.update_one = AsyncMock()
        mock_db.safety_events = MagicMock()

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        access_token = tokens["access_token"]

        response = await memory_client.post(
            "/api/v1/memory/delete_entry",
            json={"section": "people", "key": "Ravi"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_200_OK

    async def test_delete_trigger_topic(self, memory_client: Any, mock_db: MagicMock, sample_memory_doc: dict) -> None:
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.user_memory.update_one = AsyncMock()
        mock_db.safety_events = MagicMock()

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        access_token = tokens["access_token"]

        response = await memory_client.post(
            "/api/v1/memory/delete_entry",
            json={"section": "trigger_topics", "key": "exams"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_200_OK

    async def test_delete_invalid_section(self, memory_client: Any, mock_db: MagicMock, sample_memory_doc: dict) -> None:
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.safety_events = MagicMock()

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        access_token = tokens["access_token"]

        response = await memory_client.post(
            "/api/v1/memory/delete_entry",
            json={"section": "invalid", "key": "test"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
