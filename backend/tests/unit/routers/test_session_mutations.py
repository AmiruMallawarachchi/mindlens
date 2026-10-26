"""Session router behavior tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.middleware.auth import create_token_pair
from fastapi import status
from tests.unit.routers.session_test_fixtures import (
    sample_session_doc,
    sample_user_doc,
    session_client,
)

class TestDeleteSession:
    """DELETE is a real delete now.

    It used to set status="ended" and keep everything; the row disappeared
    from the sidebar only because listSessions filters ?status=active. The
    transcript, the emotion reads and the crisis records all survived a
    button labelled Delete.
    """

    @staticmethod
    def _auth() -> dict[str, str]:
        tokens = create_token_pair("user_123", "test@example.com", role="user")
        return {"Authorization": f"Bearer {tokens['access_token']}"}

    @staticmethod
    def _mocks(mock_db: MagicMock, user_doc: dict, session_doc: dict | None) -> None:
        mock_db.users.find_one = AsyncMock(return_value=user_doc)
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.sessions.find_one = AsyncMock(return_value=session_doc)
        mock_db.sessions.delete_one = AsyncMock(return_value=MagicMock(deleted_count=1))
        mock_db.mood_logs.delete_many = AsyncMock(return_value=MagicMock(deleted_count=4))
        mock_db.safety_events.delete_many = AsyncMock(return_value=MagicMock(deleted_count=2))

    async def test_delete_removes_every_session_scoped_collection(
        self, session_client: Any, mock_db: MagicMock, sample_user_doc: dict, sample_session_doc: dict
    ) -> None:
        self._mocks(mock_db, sample_user_doc, sample_session_doc)

        response = await session_client.delete(
            "/api/v1/sessions/sess_abc", headers=self._auth()
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["deleted"] == {
            "sessions": 1,
            "mood_logs": 4,
            "safety_events": 2,
        }
        mock_db.sessions.delete_one.assert_awaited_once()
        mock_db.mood_logs.delete_many.assert_awaited_once()
        mock_db.safety_events.delete_many.assert_awaited_once()

    async def test_delete_does_not_merely_flag_the_session(
        self, session_client: Any, mock_db: MagicMock, sample_user_doc: dict, sample_session_doc: dict
    ) -> None:
        """The regression that mattered: no update_one anywhere near this."""
        self._mocks(mock_db, sample_user_doc, sample_session_doc)
        mock_db.sessions.update_one = AsyncMock()

        await session_client.delete("/api/v1/sessions/sess_abc", headers=self._auth())

        mock_db.sessions.update_one.assert_not_awaited()

    async def test_every_delete_filters_by_user_id(
        self, session_client: Any, mock_db: MagicMock, sample_user_doc: dict, sample_session_doc: dict
    ) -> None:
        """Rule 6 — a guessed session id must not delete another user's data,
        so user_id is in every filter, not just the lookup."""
        self._mocks(mock_db, sample_user_doc, sample_session_doc)

        await session_client.delete("/api/v1/sessions/sess_abc", headers=self._auth())

        expected = {"session_id": "sess_abc", "user_id": "user_123"}
        assert mock_db.sessions.delete_one.call_args[0][0] == expected
        assert mock_db.mood_logs.delete_many.call_args[0][0] == expected
        assert mock_db.safety_events.delete_many.call_args[0][0] == expected

    async def test_delete_session_not_found(
        self, session_client: Any, mock_db: MagicMock, sample_user_doc: dict
    ) -> None:
        self._mocks(mock_db, sample_user_doc, None)

        response = await session_client.delete(
            "/api/v1/sessions/nonexistent", headers=self._auth()
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        mock_db.sessions.delete_one.assert_not_awaited()

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
