"""Tests for MindLens Journal Router."""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.middleware.auth import create_token_pair
from fastapi import status


@pytest.fixture
async def journal_client(mock_db: MagicMock):
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


def _auth_header() -> dict[str, str]:
    tokens = create_token_pair("user_123", "test@example.com", role="user")
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
def sample_entry() -> dict[str, Any]:
    now = datetime.datetime.now(datetime.UTC)
    return {
        "entry_id": "entry_abc",
        "user_id": "user_123",
        "title": "A hard day",
        "text": "Today was rough but I got through it.",
        "prompt_used": None,
        "created_at": now,
        "updated_at": now,
    }


class TestDailyPrompt:
    async def test_returns_a_prompt(self, journal_client: Any, mock_db: MagicMock) -> None:
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)

        response = await journal_client.get(
            "/api/v1/journal/prompt", headers=_auth_header()
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["prompt"]
        assert data["date"] == datetime.datetime.now(datetime.UTC).date().isoformat()

    async def test_prompt_is_stable_within_a_day(
        self, journal_client: Any, mock_db: MagicMock
    ) -> None:
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)

        first = await journal_client.get("/api/v1/journal/prompt", headers=_auth_header())
        second = await journal_client.get("/api/v1/journal/prompt", headers=_auth_header())
        assert first.json()["prompt"] == second.json()["prompt"]


class TestCreateEntry:
    async def test_create_entry(
        self, journal_client: Any, mock_db: MagicMock, sample_entry: dict
    ) -> None:
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.journal_entries.insert_one = AsyncMock()

        response = await journal_client.post(
            "/api/v1/journal",
            json={"title": "A hard day", "text": "Today was rough but I got through it."},
            headers=_auth_header(),
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["title"] == "A hard day"
        assert data["text"] == "Today was rough but I got through it."
        assert "entry_id" in data
        mock_db.journal_entries.insert_one.assert_awaited_once()

    async def test_create_entry_requires_text(
        self, journal_client: Any, mock_db: MagicMock
    ) -> None:
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)

        response = await journal_client.post(
            "/api/v1/journal",
            json={"title": "Empty"},
            headers=_auth_header(),
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestListEntries:
    async def test_list_entries_returns_excerpts(
        self, journal_client: Any, mock_db: MagicMock, sample_entry: dict
    ) -> None:
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)

        class _Cursor:
            def sort(self, *a, **k):
                return self

            def skip(self, *a, **k):
                return self

            def limit(self, *a, **k):
                return self

            def __aiter__(self):
                async def gen():
                    yield sample_entry
                return gen()

        mock_db.journal_entries.find = MagicMock(return_value=_Cursor())

        response = await journal_client.get("/api/v1/journal", headers=_auth_header())
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["entry_id"] == "entry_abc"
        assert data[0]["excerpt"] == "Today was rough but I got through it."


class TestGetEntry:
    async def test_get_entry_success(
        self, journal_client: Any, mock_db: MagicMock, sample_entry: dict
    ) -> None:
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.journal_entries.find_one = AsyncMock(return_value=sample_entry)

        response = await journal_client.get(
            "/api/v1/journal/entry_abc", headers=_auth_header()
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["entry_id"] == "entry_abc"

    async def test_get_entry_not_found(self, journal_client: Any, mock_db: MagicMock) -> None:
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.journal_entries.find_one = AsyncMock(return_value=None)

        response = await journal_client.get(
            "/api/v1/journal/missing", headers=_auth_header()
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestUpdateEntry:
    async def test_update_entry_success(
        self, journal_client: Any, mock_db: MagicMock, sample_entry: dict
    ) -> None:
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.journal_entries.find_one = AsyncMock(return_value=sample_entry)
        mock_db.journal_entries.update_one = AsyncMock()

        response = await journal_client.put(
            "/api/v1/journal/entry_abc",
            json={"title": "Updated", "text": "Feeling a bit better now."},
            headers=_auth_header(),
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["text"] == "Feeling a bit better now."

    async def test_update_entry_not_found(
        self, journal_client: Any, mock_db: MagicMock
    ) -> None:
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.journal_entries.find_one = AsyncMock(return_value=None)

        response = await journal_client.put(
            "/api/v1/journal/missing",
            json={"text": "irrelevant"},
            headers=_auth_header(),
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestDeleteEntry:
    async def test_delete_entry_success(
        self, journal_client: Any, mock_db: MagicMock
    ) -> None:
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.journal_entries.delete_one = AsyncMock(
            return_value=MagicMock(deleted_count=1)
        )

        response = await journal_client.delete(
            "/api/v1/journal/entry_abc", headers=_auth_header()
        )
        assert response.status_code == status.HTTP_200_OK

    async def test_delete_entry_not_found(
        self, journal_client: Any, mock_db: MagicMock
    ) -> None:
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.journal_entries.delete_one = AsyncMock(
            return_value=MagicMock(deleted_count=0)
        )

        response = await journal_client.delete(
            "/api/v1/journal/missing", headers=_auth_header()
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
