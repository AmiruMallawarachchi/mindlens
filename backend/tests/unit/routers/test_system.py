"""Unit tests for the admin-only hosted-service status routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

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
        from app.routers import system

        rag = {"provider": "pinecone", "status": "reachable", "dimension": 1024}
        with (
            patch.object(system.settings, "groq_api_key", "test-groq-key"),
            patch.object(system, "rag_status", AsyncMock(return_value=rag)),
        ):
            response = await admin_client.get("/api/v1/admin/system")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["database"] == "connected"
        assert body["inference"] == {"provider": "groq", "status": "configured"}
        assert body["rag"] == rag
        assert body["observability"]["provider"] == "langfuse"
        assert "environment" in body
        assert "timestamp" in body
        mock_db.client.admin.command.assert_awaited_once_with("ping")

    async def test_rag_status_is_probed_not_assumed(
        self, admin_client: AsyncClient, mock_db: MagicMock
    ) -> None:
        """The endpoint used to derive rag.status from the presence of a key
        string, so a rejected key still reported "configured". It now has to
        ask, and has to pass along whatever the answer was."""
        from app.routers import system

        rejected = {
            "provider": "pinecone",
            "status": "unauthorized",
            "detail": "the API key was rejected",
        }
        with patch.object(system, "rag_status", AsyncMock(return_value=rejected)) as probe:
            response = await admin_client.get("/api/v1/admin/system")

        probe.assert_awaited_once()
        assert response.json()["rag"] == rejected

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

    async def test_returns_hosted_service_health(
        self, admin_client: AsyncClient
    ) -> None:
        from app.routers import system

        rag = {"provider": "pinecone", "status": "not_configured"}
        with (
            patch.object(system.settings, "groq_api_key", "test-groq-key"),
            patch.object(system.settings, "langfuse_enabled", True),
            patch.object(system, "rag_status", AsyncMock(return_value=rag)),
        ):
            response = await admin_client.get("/api/v1/admin/models")

        assert response.status_code == 200
        assert response.json() == {
            "inference": {"provider": "groq", "status": "configured"},
            "rag": rag,
            "observability": {"provider": "langfuse", "enabled": True},
        }
