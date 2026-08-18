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

    async def test_end_session_with_naive_started_at(self, session_client: Any, mock_db: MagicMock, sample_user_doc: dict, sample_session_doc: dict) -> None:
        """Motor returns datetimes timezone-NAIVE, which is what this endpoint
        actually receives in production.

        sample_session_doc uses an aware datetime, so test_end_session_success
        above passed while every real call 500'd on
        "can't subtract offset-naive and offset-aware datetimes". This pins the
        realistic shape so the regression can't come back silently.
        """
        naive_doc = dict(sample_session_doc)
        naive_doc["started_at"] = datetime.datetime.utcnow()  # noqa: DTZ003 - mirrors Motor

        mock_db.users.find_one = AsyncMock(return_value=sample_user_doc)
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.sessions.find_one = AsyncMock(return_value=naive_doc)
        mock_db.sessions.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
        mock_db.safety_events = MagicMock()

        tokens = create_token_pair("user_123", "test@example.com", role="user")

        response = await session_client.delete(
            "/api/v1/sessions/sess_abc",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "ended"
        # The duration is what the arithmetic produces; a non-negative int
        # proves the subtraction actually ran rather than raising.
        assert isinstance(data["duration_seconds"], int)
        assert data["duration_seconds"] >= 0

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


class TestRenameSession:
    """PATCH /{session_id}/title.

    `title` was writable only at creation before this route existed, and the
    chat flow never passed one — so every session a user started showed as a
    bare date and there was no way to change it.
    """

    @staticmethod
    def _auth() -> dict[str, str]:
        tokens = create_token_pair("user_123", "test@example.com", role="user")
        return {"Authorization": f"Bearer {tokens['access_token']}"}

    @staticmethod
    def _base_mocks(mock_db: MagicMock, user_doc: dict) -> None:
        mock_db.users.find_one = AsyncMock(return_value=user_doc)
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.safety_events = MagicMock()

    async def test_rename_session_success(
        self, session_client: Any, mock_db: MagicMock, sample_user_doc: dict, sample_session_doc: dict
    ) -> None:
        self._base_mocks(mock_db, sample_user_doc)
        renamed = {**sample_session_doc, "title": "Two weeks to the viva"}
        mock_db.sessions.find_one_and_update = AsyncMock(return_value=renamed)

        response = await session_client.patch(
            "/api/v1/sessions/sess_abc/title",
            json={"title": "Two weeks to the viva"},
            headers=self._auth(),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["title"] == "Two weeks to the viva"

    async def test_rename_filters_by_user_id(
        self, session_client: Any, mock_db: MagicMock, sample_user_doc: dict, sample_session_doc: dict
    ) -> None:
        """Rule 6 — a user must not be able to rename someone else's session
        by guessing its id, so user_id is part of the query, not just the
        session_id."""
        self._base_mocks(mock_db, sample_user_doc)
        mock_db.sessions.find_one_and_update = AsyncMock(return_value=sample_session_doc)

        await session_client.patch(
            "/api/v1/sessions/sess_abc/title",
            json={"title": "Renamed"},
            headers=self._auth(),
        )

        query = mock_db.sessions.find_one_and_update.call_args[0][0]
        assert query == {"session_id": "sess_abc", "user_id": "user_123"}

    async def test_rename_sets_only_title_and_timestamp(
        self, session_client: Any, mock_db: MagicMock, sample_user_doc: dict, sample_session_doc: dict
    ) -> None:
        """Rule 6 — a partial update, never a whole-subdocument $set that
        would take the transcript with it."""
        self._base_mocks(mock_db, sample_user_doc)
        mock_db.sessions.find_one_and_update = AsyncMock(return_value=sample_session_doc)

        await session_client.patch(
            "/api/v1/sessions/sess_abc/title",
            json={"title": "Renamed"},
            headers=self._auth(),
        )

        update = mock_db.sessions.find_one_and_update.call_args[0][1]
        assert set(update["$set"]) == {"title", "updated_at"}

    async def test_rename_strips_surrounding_whitespace(
        self, session_client: Any, mock_db: MagicMock, sample_user_doc: dict, sample_session_doc: dict
    ) -> None:
        self._base_mocks(mock_db, sample_user_doc)
        mock_db.sessions.find_one_and_update = AsyncMock(return_value=sample_session_doc)

        await session_client.patch(
            "/api/v1/sessions/sess_abc/title",
            json={"title": "   Padded title   "},
            headers=self._auth(),
        )

        update = mock_db.sessions.find_one_and_update.call_args[0][1]
        assert update["$set"]["title"] == "Padded title"

    @pytest.mark.parametrize("bad_title", ["", "   ", "\t\n", "x" * 201])
    async def test_rename_rejects_blank_or_overlong(
        self, session_client: Any, mock_db: MagicMock, sample_user_doc: dict, bad_title: str
    ) -> None:
        """A whitespace-only title would render as an empty sidebar row that
        still suppresses the date fallback — an invisible conversation."""
        self._base_mocks(mock_db, sample_user_doc)
        mock_db.sessions.find_one_and_update = AsyncMock()

        response = await session_client.patch(
            "/api/v1/sessions/sess_abc/title",
            json={"title": bad_title},
            headers=self._auth(),
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        mock_db.sessions.find_one_and_update.assert_not_called()

    async def test_rename_session_not_found(
        self, session_client: Any, mock_db: MagicMock, sample_user_doc: dict
    ) -> None:
        self._base_mocks(mock_db, sample_user_doc)
        mock_db.sessions.find_one_and_update = AsyncMock(return_value=None)

        response = await session_client.patch(
            "/api/v1/sessions/nonexistent/title",
            json={"title": "Renamed"},
            headers=self._auth(),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_rename_requires_auth(self, session_client: Any, mock_db: MagicMock) -> None:
        response = await session_client.patch(
            "/api/v1/sessions/sess_abc/title", json={"title": "Renamed"}
        )
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )
