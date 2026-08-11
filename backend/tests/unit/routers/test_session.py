"""Tests for MindLens Session REST Router."""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.middleware.auth import create_token_pair
from fastapi import status


def _make_async_cursor(docs: list[dict]) -> Any:
    """Return a mock MongoDB cursor that works with async for."""

    async def _async_generator():
        for doc in docs:
            yield doc

    class _Cursor:
        def __init__(self, docs: list[dict]) -> None:
            self._docs = docs

        def skip(self, n: int) -> _Cursor:
            return self

        def limit(self, n: int) -> _Cursor:
            return self

        def sort(self, *args, **kwargs) -> _Cursor:
            return self

        def __aiter__(self) -> Any:
            return _async_generator().__aiter__()

    return _Cursor(docs)


@pytest.fixture
async def session_client(mock_db: MagicMock):
    """FastAPI test client with mocked DB for session tests."""
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
def sample_user_doc() -> dict[str, Any]:
    return {
        "_id": "user_123",
        "email": "test@example.com",
        "name": "Amiru",
        "nickname": "Ami",
        "age": 22,
        "age_group": "adult",
        "role": "user",
        "is_active": True,
        "onboarding_complete": False,
        "created_at": datetime.datetime.now(datetime.UTC),
    }


@pytest.fixture
def sample_session_doc() -> dict[str, Any]:
    return {
        "session_id": "sess_abc",
        "user_id": "user_123",
        "title": "Exam stress",
        "context": None,
        "started_at": datetime.datetime.now(datetime.UTC),
        "ended_at": None,
        "status": "active",
        "turns": [],
        "eos_timeline": [],
        "session_summary": "",
        "key_facts": [],
        "agents_used": [],
        "primary_modality": None,
        "music_played": [],
        "check_in_scheduled": False,
        "updated_at": datetime.datetime.now(datetime.UTC),
    }


class TestCreateSession:
    async def test_create_session_success(self, session_client: Any, mock_db: MagicMock, sample_user_doc: dict) -> None:
        mock_db.users.find_one = AsyncMock(return_value=sample_user_doc)
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        # No reusable empty session on file — falls through to creating one.
        mock_db.sessions.find_one = AsyncMock(return_value=None)
        mock_db.sessions.insert_one = AsyncMock(return_value=MagicMock(inserted_id="sess_abc"))
        mock_db.safety_events = MagicMock()

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        access_token = tokens["access_token"]

        response = await session_client.post(
            "/api/v1/sessions",
            json={"title": "Exam stress", "context": "Finals next week"},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["user_id"] == "user_123"
        assert data["status"] == "active"
        assert "session_id" in data
        assert data["title"] == "Exam stress"

    async def test_create_session_reuses_empty_active_session(
        self, session_client: Any, mock_db: MagicMock, sample_user_doc: dict, sample_session_doc: dict
    ) -> None:
        """A zero-turn active session on file is returned instead of minting
        another — this is what stops a page reload from filling the sidebar
        with empty sessions and inflating the dashboard's session count."""
        mock_db.users.find_one = AsyncMock(return_value=sample_user_doc)
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.sessions.find_one = AsyncMock(return_value=sample_session_doc)
        mock_db.sessions.insert_one = AsyncMock()
        mock_db.safety_events = MagicMock()

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        access_token = tokens["access_token"]

        response = await session_client.post(
            "/api/v1/sessions",
            json={},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["session_id"] == sample_session_doc["session_id"]
        mock_db.sessions.insert_one.assert_not_called()

    async def test_create_session_no_token(self, session_client: Any, mock_db: MagicMock) -> None:
        response = await session_client.post("/api/v1/sessions", json={"title": "No auth"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_create_session_invalid_token(self, session_client: Any, mock_db: MagicMock) -> None:
        response = await session_client.post(
            "/api/v1/sessions",
            json={"title": "Bad token"},
            headers={"Authorization": "Bearer bad_token"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestListSessions:
    async def test_list_sessions(self, session_client: Any, mock_db: MagicMock, sample_user_doc: dict, sample_session_doc: dict) -> None:
        mock_db.users.find_one = AsyncMock(return_value=sample_user_doc)
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.safety_events = MagicMock()
        cursor = _make_async_cursor([sample_session_doc])
        mock_db.sessions.find = MagicMock(return_value=cursor)

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        access_token = tokens["access_token"]

        response = await session_client.get(
            "/api/v1/sessions",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["session_id"] == "sess_abc"
        assert data[0]["status"] == "active"

    async def test_list_sessions_filter_status(self, session_client: Any, mock_db: MagicMock, sample_user_doc: dict) -> None:
        mock_db.users.find_one = AsyncMock(return_value=sample_user_doc)
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.safety_events = MagicMock()

        cursor = _make_async_cursor([])
        mock_db.sessions.find = MagicMock(return_value=cursor)

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        access_token = tokens["access_token"]

        response = await session_client.get(
            "/api/v1/sessions?status=ended",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK


class TestGetSession:
    async def test_get_session_success(self, session_client: Any, mock_db: MagicMock, sample_user_doc: dict, sample_session_doc: dict) -> None:
        mock_db.users.find_one = AsyncMock(return_value=sample_user_doc)
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.sessions.find_one = AsyncMock(return_value=sample_session_doc)
        mock_db.safety_events = MagicMock()

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        access_token = tokens["access_token"]

        response = await session_client.get(
            "/api/v1/sessions/sess_abc",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["session_id"] == "sess_abc"
        assert data["user_id"] == "user_123"

    async def test_get_session_not_found(self, session_client: Any, mock_db: MagicMock, sample_user_doc: dict) -> None:
        mock_db.users.find_one = AsyncMock(return_value=sample_user_doc)
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.sessions.find_one = AsyncMock(return_value=None)
        mock_db.safety_events = MagicMock()

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        access_token = tokens["access_token"]

        response = await session_client.get(
            "/api/v1/sessions/nonexistent",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


    async def test_get_session_wrong_owner(self, session_client: Any, mock_db: MagicMock, sample_user_doc: dict, sample_session_doc: dict) -> None:
        mock_db.users.find_one = AsyncMock(return_value=sample_user_doc)
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        # Return None because session belongs to different user
        mock_db.sessions.find_one = AsyncMock(return_value=None)
        mock_db.safety_events = MagicMock()

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        access_token = tokens["access_token"]

        response = await session_client.get(
            "/api/v1/sessions/other_users_session",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestEndSession:
    async def test_end_session_success(self, session_client: Any, mock_db: MagicMock, sample_user_doc: dict, sample_session_doc: dict) -> None:
        mock_db.users.find_one = AsyncMock(return_value=sample_user_doc)
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.sessions.find_one = AsyncMock(return_value=sample_session_doc)
        mock_db.sessions.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
        mock_db.safety_events = MagicMock()

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        access_token = tokens["access_token"]

        response = await session_client.delete(
            "/api/v1/sessions/sess_abc",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["session_id"] == "sess_abc"
        assert data["status"] == "ended"
        assert "ended_at" in data

    async def test_end_session_already_ended(self, session_client: Any, mock_db: MagicMock, sample_user_doc: dict, sample_session_doc: dict) -> None:
        ended_doc = dict(sample_session_doc)
        ended_doc["status"] = "ended"
        ended_doc["ended_at"] = datetime.datetime.now(datetime.UTC)

        mock_db.users.find_one = AsyncMock(return_value=sample_user_doc)
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.sessions.find_one = AsyncMock(return_value=ended_doc)
        mock_db.safety_events = MagicMock()

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        access_token = tokens["access_token"]

        response = await session_client.delete(
            "/api/v1/sessions/sess_abc",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_end_session_not_found(self, session_client: Any, mock_db: MagicMock, sample_user_doc: dict) -> None:
        mock_db.users.find_one = AsyncMock(return_value=sample_user_doc)
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.sessions.find_one = AsyncMock(return_value=None)
        mock_db.safety_events = MagicMock()

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        access_token = tokens["access_token"]

        response = await session_client.delete(
            "/api/v1/sessions/nonexistent",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
