"""Unit tests for health/readiness, security headers, and error handling."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.main import app
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


class TestHealthCheck:
    async def test_health_reports_ok(self, client: AsyncClient) -> None:
        response = await client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["version"] == "0.4.0"

    async def test_health_needs_no_auth(self, client: AsyncClient) -> None:
        """A health probe gated behind a login is not a health probe."""
        response = await client.get("/health")
        assert response.status_code != 401


class TestSecurityHeaders:
    async def test_present_on_every_response(self, client: AsyncClient) -> None:
        response = await client.get("/health")
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["Referrer-Policy"] == "no-referrer"
        assert response.headers["Cache-Control"] == "no-store"

    async def test_hsts_absent_outside_production(self, client: AsyncClient) -> None:
        """settings.is_production is False in the test environment — HSTS
        pinning HTTPS on a non-production origin would be the wrong claim
        for local dev and CI."""
        response = await client.get("/health")
        assert "Strict-Transport-Security" not in response.headers

    async def test_hsts_present_in_production(self, client: AsyncClient) -> None:
        # is_production is a computed property (app_env == "production"),
        # not a patchable attribute — its backing field is what has to move.
        with patch("app.main.settings.app_env", "production"):
            response = await client.get("/health")
        assert "Strict-Transport-Security" in response.headers


class TestReadinessCheck:
    @pytest.fixture(autouse=True)
    def _db_client(self):
        """get_db_client is what /ready calls to reach Mongo; every test
        here controls what it returns rather than touching a real driver."""
        with patch("app.main.get_db_client") as mock:
            fake_client = MagicMock()
            fake_client.admin.command = AsyncMock(return_value={"ok": 1})
            mock.return_value = fake_client
            yield mock

    async def test_ready_when_db_and_groq_configured(
        self, client: AsyncClient
    ) -> None:
        """V2 readiness requires MongoDB and configured hosted inference."""
        with (
            patch("app.main.settings.groq_api_key", "test-groq-key"),
            patch("app.main.settings.use_openai_stubs", False),
            patch("app.main.settings.pinecone_api_key", "test-pinecone-key"),
            patch("app.main.settings.pinecone_index_name", "test-index"),
        ):
            response = await client.get("/ready")
        assert response.status_code == 200
        body = response.json()
        assert body["ready"] is True
        assert body["database"] == "connected"
        assert body["inference"] == {
            "provider": "groq",
            "status": "configured",
            "stub_mode": False,
        }
        assert body["rag"] == {
            "provider": "pinecone",
            "status": "configured",
            "mode": "fail_soft",
        }
        assert body["observability"]["provider"] == "langfuse"

    async def test_not_ready_in_stub_mode(self, client: AsyncClient) -> None:
        """A key is not enough if the deployment is still serving stubs."""
        with (
            patch("app.main.settings.groq_api_key", "test-groq-key"),
            patch("app.main.settings.use_openai_stubs", True),
        ):
            response = await client.get("/ready")
        assert response.status_code == 503
        body = response.json()
        assert body["ready"] is False
        assert body["inference"] == {
            "provider": "groq",
            "status": "stub_mode",
            "stub_mode": True,
        }

    async def test_not_ready_when_db_unreachable(self, client: AsyncClient) -> None:
        with patch("app.main.get_db_client") as mock:
            mock.return_value = None
            response = await client.get("/ready")
        assert response.status_code == 503
        assert response.json()["ready"] is False
        assert response.json()["database"] == "disconnected"

    async def test_not_ready_when_ping_raises(self, client: AsyncClient) -> None:
        with patch("app.main.get_db_client") as mock:
            fake_client = MagicMock()
            fake_client.admin.command = AsyncMock(side_effect=ConnectionError("down"))
            mock.return_value = fake_client
            response = await client.get("/ready")
        assert response.status_code == 503
        assert response.json()["ready"] is False

    async def test_not_ready_when_groq_key_missing(self, client: AsyncClient) -> None:
        with (
            patch("app.main.settings.groq_api_key", ""),
            patch("app.main.settings.use_openai_stubs", False),
        ):
            response = await client.get("/ready")
        assert response.status_code == 503
        body = response.json()
        assert body["ready"] is False
        assert body["database"] == "connected"
        assert body["inference"] == {
            "provider": "groq",
            "status": "missing_key",
            "stub_mode": False,
        }

    @pytest.mark.parametrize(
        ("api_key", "index_name"),
        [("", "test-index"), ("test-pinecone-key", "")],
    )
    async def test_pinecone_configuration_is_reported_without_blocking_readiness(
        self,
        client: AsyncClient,
        api_key: str,
        index_name: str,
    ) -> None:
        """Pinecone is fail-soft; /ready reports configuration, not reachability."""
        with (
            patch("app.main.settings.groq_api_key", "test-groq-key"),
            patch("app.main.settings.use_openai_stubs", False),
            patch("app.main.settings.pinecone_api_key", api_key),
            patch("app.main.settings.pinecone_index_name", index_name),
        ):
            response = await client.get("/ready")

        assert response.status_code == 200
        body = response.json()
        assert body["ready"] is True
        assert body["rag"] == {
            "provider": "pinecone",
            "status": "not_configured",
            "mode": "fail_soft",
        }


class TestGlobalExceptionHandler:
    async def test_unhandled_exception_returns_generic_500(
        self, client: AsyncClient
    ) -> None:
        """An unhandled exception must reach the user as a generic message,
        never the raw exception text — a stack trace in a mental-health
        app's error response is its own kind of leak.

        /health has no try/except of its own, so a genuine, uncaught
        exception inside it (render_git_commit not being sliceable) is what
        actually reaches the global handler — not a route that happens to
        already catch its own errors.

        A plain ASGITransport re-raises the exception to the test even
        though app.exception_handler already turned it into a real 500 —
        that's ASGITransport's default raise_app_exceptions=True, meant for
        surfacing bugs during testing. It's disabled here specifically to
        observe what a real client actually receives.
        """
        no_raise_client = AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        )
        with patch("app.main.settings.render_git_commit", None):
            async with no_raise_client as c:
                response = await c.get("/health")
        assert response.status_code == 500
        body = response.json()
        assert body["detail"] == "Internal server error"
        assert "request_id" in body
        assert "TypeError" not in str(body)
        assert "render_git_commit" not in str(body)
