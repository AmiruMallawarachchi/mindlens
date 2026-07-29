"""Tests for MindLens Dashboard Router."""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.middleware.auth import create_token_pair
from fastapi import status


@pytest.fixture
async def dashboard_client(mock_db: MagicMock):
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


class TestGetMoodLogs:
    async def test_returns_mood_list(self, dashboard_client: Any, mock_db: MagicMock) -> None:
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        cursor = MagicMock()
        cursor.sort.return_value = cursor
        cursor.limit.return_value = cursor
        cursor.to_list = AsyncMock(return_value=[{"surface_emotion": "joy"}])
        mock_db.mood_logs.find = MagicMock(return_value=cursor)

        response = await dashboard_client.get(
            "/api/v1/dashboard/mood", headers=_auth_header()
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"moods": [{"surface_emotion": "joy"}]}


class TestGetDashboardSummary:
    async def test_returns_summary(self, dashboard_client: Any, mock_db: MagicMock) -> None:
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.sessions.count_documents = AsyncMock(return_value=3)
        mock_db.user_memory.find_one = AsyncMock(return_value={"profile": {}})
        cursor = MagicMock()
        cursor.sort.return_value = cursor
        cursor.limit.return_value = cursor
        cursor.to_list = AsyncMock(return_value=[])
        mock_db.mood_logs.find = MagicMock(return_value=cursor)

        response = await dashboard_client.get(
            "/api/v1/dashboard/summary", headers=_auth_header()
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["session_count"] == 3
        assert data["memory_enabled"] is True


class TestGetProgressInsight:
    async def test_not_enough_sessions(self, dashboard_client: Any, mock_db: MagicMock) -> None:
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.sessions.count_documents = AsyncMock(return_value=2)

        response = await dashboard_client.get(
            "/api/v1/dashboard/insight", headers=_auth_header()
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["available"] is False
        assert data["sessions_needed"] == 5

    async def test_generates_fresh_insight(
        self, dashboard_client: Any, mock_db: MagicMock
    ) -> None:
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.sessions.count_documents = AsyncMock(return_value=7)
        mock_db.progress_insights.find_one = AsyncMock(return_value=None)
        mock_db.progress_insights.update_one = AsyncMock()
        mock_db.users.find_one = AsyncMock(
            return_value={"_id": "user_123", "nickname": "Amiru", "age_group": "adult"}
        )
        cursor = MagicMock()
        cursor.sort.return_value = cursor
        cursor.limit.return_value = cursor
        cursor.to_list = AsyncMock(
            return_value=[
                {"surface_emotion": "joy", "distress_level": 0.3},
                {"surface_emotion": "calm", "distress_level": 0.2},
            ]
        )
        mock_db.mood_logs.find = MagicMock(return_value=cursor)

        mock_output = MagicMock(text="You've been showing up consistently, Amiru.")
        with patch(
            "app.routers.dashboard.ProgressAgent.run",
            new=AsyncMock(return_value=mock_output),
        ):
            response = await dashboard_client.get(
                "/api/v1/dashboard/insight", headers=_auth_header()
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["available"] is True
        assert data["insight"] == "You've been showing up consistently, Amiru."
        mock_db.progress_insights.update_one.assert_awaited_once()

    async def test_returns_cached_insight_before_regeneration_window(
        self, dashboard_client: Any, mock_db: MagicMock
    ) -> None:
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.sessions.count_documents = AsyncMock(return_value=9)
        mock_db.progress_insights.find_one = AsyncMock(
            return_value={
                "insight": "Cached insight text.",
                "generated_at": datetime.datetime.now(datetime.UTC),
                "session_count_at_generation": 7,
            }
        )

        response = await dashboard_client.get(
            "/api/v1/dashboard/insight", headers=_auth_header()
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["insight"] == "Cached insight text."

    async def test_regenerates_after_seven_more_sessions(
        self, dashboard_client: Any, mock_db: MagicMock
    ) -> None:
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.sessions.count_documents = AsyncMock(return_value=14)
        mock_db.progress_insights.find_one = AsyncMock(
            return_value={
                "insight": "Old insight.",
                "generated_at": datetime.datetime.now(datetime.UTC),
                "session_count_at_generation": 7,
            }
        )
        mock_db.progress_insights.update_one = AsyncMock()
        mock_db.users.find_one = AsyncMock(
            return_value={"_id": "user_123", "nickname": "Amiru", "age_group": "adult"}
        )
        cursor = MagicMock()
        cursor.sort.return_value = cursor
        cursor.limit.return_value = cursor
        cursor.to_list = AsyncMock(return_value=[])
        mock_db.mood_logs.find = MagicMock(return_value=cursor)

        mock_output = MagicMock(text="A fresh insight.")
        with patch(
            "app.routers.dashboard.ProgressAgent.run",
            new=AsyncMock(return_value=mock_output),
        ):
            response = await dashboard_client.get(
                "/api/v1/dashboard/insight", headers=_auth_header()
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["insight"] == "A fresh insight."
        mock_db.progress_insights.update_one.assert_awaited_once()

    async def test_generation_failure_is_reported_not_raised(
        self, dashboard_client: Any, mock_db: MagicMock
    ) -> None:
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.sessions.count_documents = AsyncMock(return_value=7)
        mock_db.progress_insights.find_one = AsyncMock(return_value=None)
        mock_db.users.find_one = AsyncMock(
            return_value={"_id": "user_123", "nickname": "Amiru", "age_group": "adult"}
        )
        cursor = MagicMock()
        cursor.sort.return_value = cursor
        cursor.limit.return_value = cursor
        cursor.to_list = AsyncMock(return_value=[])
        mock_db.mood_logs.find = MagicMock(return_value=cursor)

        with patch(
            "app.routers.dashboard.ProgressAgent.run",
            new=AsyncMock(side_effect=RuntimeError("groq down")),
        ):
            response = await dashboard_client.get(
                "/api/v1/dashboard/insight", headers=_auth_header()
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["available"] is True
        assert data["insight"] is None
        assert "error" in data
