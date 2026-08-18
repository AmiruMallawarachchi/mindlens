"""Unit tests for app.main — health/readiness, security headers, the
global exception handler.

No test file existed for this module. `/ready` in particular has real
branching logic (DB down, models not preloaded, models loading, RAG empty)
that an operator relies on to know whether it's safe to route traffic here
— an untested readiness probe that always reports healthy is worse than no
probe at all.

The lifespan context manager (DB connect, model warmup, RAG ingest on
startup) is deliberately not covered here: exercising it means mocking the
DB driver, the model loader and the RAG ingester all the way down, which
turns a unit test into an integration test. Its pieces (connect_db,
model_manager.warmup_all, ingest_documents) already have their own test
files; this one covers what main.py itself decides.
"""

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

    async def test_ready_when_db_reachable_and_preload_off(
        self, client: AsyncClient
    ) -> None:
        """With preload_models/preload_rag both off (the test default),
        readiness must not wait on either — a model_ready check gated on a
        feature that's disabled would report perpetually unready."""
        with (
            patch("app.main.settings.preload_models", False),
            patch("app.main.settings.preload_rag", False),
        ):
            response = await client.get("/ready")
        assert response.status_code == 200
        body = response.json()
        assert body["ready"] is True
        assert body["database"] == "connected"
        assert body["rag"] == {"status": "lazy"}

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

    async def test_waits_on_models_when_preload_enabled(
        self, client: AsyncClient
    ) -> None:
        """preload_models=true is the production posture (chat.py's
        history: it was false, made the first real user absorb a 4-way
        concurrent cold load, and timed out). /ready must gate on every
        model actually being "ready", not just that the process is up."""
        with (
            patch("app.main.settings.preload_models", True),
            patch("app.main.settings.preload_rag", False),
            patch("app.main.model_manager.health_status") as health,
        ):
            health.return_value = {
                "emotion": {"status": "loading"},
                "crisis": {"status": "ready"},
            }
            response = await client.get("/ready")
        assert response.status_code == 503
        assert response.json()["ready"] is False

    async def test_ready_when_all_preloaded_models_report_ready(
        self, client: AsyncClient
    ) -> None:
        with (
            patch("app.main.settings.preload_models", True),
            patch("app.main.settings.preload_rag", False),
            patch("app.main.model_manager.health_status") as health,
        ):
            health.return_value = {
                "emotion": {"status": "ready"},
                "crisis": {"status": "ready"},
            }
            response = await client.get("/ready")
        assert response.status_code == 200
        assert response.json()["ready"] is True

    async def test_rag_empty_is_reported_and_blocks_readiness(
        self, client: AsyncClient
    ) -> None:
        """Zero chunks with RAG preload on means ingestion silently produced
        nothing — the same failure the startup RuntimeError guards against,
        but at request time instead of boot time. Must not read as ready."""
        with (
            patch("app.main.settings.preload_models", False),
            patch("app.main.settings.preload_rag", True),
            patch("app.main.get_vector_store") as store,
        ):
            store.return_value.count.return_value = 0
            response = await client.get("/ready")
        assert response.status_code == 503
        body = response.json()
        assert body["rag"] == {"status": "empty", "chunks": 0}

    async def test_rag_populated_reports_chunk_count(self, client: AsyncClient) -> None:
        with (
            patch("app.main.settings.preload_models", False),
            patch("app.main.settings.preload_rag", True),
            patch("app.main.get_vector_store") as store,
        ):
            store.return_value.count.return_value = 67
            response = await client.get("/ready")
        assert response.status_code == 200
        assert response.json()["rag"] == {"status": "ready", "chunks": 67}


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
