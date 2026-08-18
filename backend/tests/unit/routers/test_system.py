"""Unit tests for the admin-only operational status routes.

No test file existed for this router before, so these endpoints had zero
coverage: an admin-auth regression or a broken model_manager.health_status()
call would have shipped silently.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.db import get_db
from app.middleware.auth import require_admin
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def mock_db() -> MagicMock:
    db = MagicMock()
    db.client = MagicMock()
    db.client.admin = MagicMock()
    db.client.admin.command = AsyncMock(return_value={"ok": 1})
    return db


@pytest.fixture
async def system_client(mock_db: MagicMock):
    """A client with the DB mocked but require_admin left real, so tests
    can choose per-test whether the caller is an admin."""
    from app.main import app

    app.dependency_overrides = {}

    async def override_get_db():
        return mock_db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def admin_client(system_client: AsyncClient):
    """Same client, with require_admin overridden to a fake admin —
    exercising the route logic without a real JWT."""
    from app.main import app

    app.dependency_overrides[require_admin] = lambda: {
        "_id": "admin_1",
        "role": "admin",
    }
    return system_client


class TestSystemStatus:
    async def test_requires_admin(self, system_client: AsyncClient) -> None:
        response = await system_client.get("/api/v1/admin/system")
        assert response.status_code in (401, 403)

    async def test_returns_operational_status(
        self, admin_client: AsyncClient, mock_db: MagicMock
    ) -> None:
        response = await admin_client.get("/api/v1/admin/system")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["database"] == "connected"
        assert "models" in body
        assert "environment" in body
        assert "timestamp" in body
        mock_db.client.admin.command.assert_awaited_once_with("ping")

    async def test_reports_disconnected_when_ping_fails(
        self, admin_client: AsyncClient, mock_db: MagicMock
    ) -> None:
        """A dead DB connection must surface as a failure, not a fabricated
        "connected" status — the honesty rule applies to admin tooling too.
        The route has no try/except around the ping, so the ASGI transport
        propagates it rather than turning it into a response; a real
        deployment's exception middleware turns that into a 500. Either way,
        the point holds: nothing here catches the failure and reports
        "connected" anyway."""
        mock_db.client.admin.command = AsyncMock(side_effect=ConnectionError("down"))

        with pytest.raises(ConnectionError):
            await admin_client.get("/api/v1/admin/system")


class TestModelStatus:
    async def test_requires_admin(self, system_client: AsyncClient) -> None:
        response = await system_client.get("/api/v1/admin/models")
        assert response.status_code in (401, 403)

    async def test_returns_model_registry_health(
        self, admin_client: AsyncClient
    ) -> None:
        response = await admin_client.get("/api/v1/admin/models")

        assert response.status_code == 200
        models = response.json()["models"]
        # The five real models this system reports on — a stale or renamed
        # entry here would mean the admin panel is showing the wrong roster.
        assert set(models.keys()) == {
            "emotion",
            "crisis",
            "mental_health",
            "distortion",
            "rag_reranker",
        }
        for entry in models.values():
            assert "status" in entry
            assert "error_count" in entry
