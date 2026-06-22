# backend/app/main.py
"""
MindLens FastAPI Application
=============================
Entry point for the backend. Handles lifespan (startup/shutdown),
router registration, CORS, middleware, and global exception handling.
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.db import connect_db, disconnect_db, get_db_client
from app.middleware import MindLensAuthMiddleware
from app.routers import (
    auth_router,
    chat_router,
    dashboard_router,
    memory_router,
    onboarding_router,
    session_router,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Lifespan context manager
# ---------------------------------------------------------------------------
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan events."""
    logger.info("MindLens backend starting up …")
    await connect_db()
    logger.info("MongoDB connected.")
    yield
    logger.info("MindLens backend shutting down …")
    await disconnect_db()
    logger.info("MongoDB disconnected. Goodbye.")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(
        title="MindLens API",
        description="Multi-agent AI system for personalized mental health support",
        version="0.4.0-alpha",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # --- CORS ---------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Auth Middleware (request ID, rate limiting, JWT extraction) ----------
    app.add_middleware(MindLensAuthMiddleware)

    # --- Routers ------------------------------------------------------------
    app.include_router(auth_router, prefix="/api/v1/auth", tags=["Authentication"])
    app.include_router(session_router, prefix="/api/v1/sessions", tags=["Session"])
    app.include_router(chat_router, prefix="/ws", tags=["WebSocket"])
    app.include_router(dashboard_router, prefix="/api/v1/dashboard", tags=["Dashboard"])
    app.include_router(onboarding_router, prefix="/api/v1/onboarding", tags=["Onboarding"])
    app.include_router(memory_router, prefix="/api/v1/memory", tags=["Memory"])


    # --- Global exception handler -------------------------------------------
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Catch-all. Logs server-side; returns safe 500 to client."""
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error. Reference logged."},
        )

    # --- Health check -------------------------------------------------------
    @app.get("/health", tags=["System"])
    async def health_check() -> dict[str, str]:
        """Liveness probe."""
        return {"status": "ok", "version": "0.4.0-alpha"}

    # --- Ready probe --------------------------------------------------------
    @app.get("/ready", tags=["System"])
    async def readiness_check() -> JSONResponse:
        """
        Readiness probe. Checks MongoDB connectivity.
        Returns JSONResponse so we can send 503 on failure.
        """
        try:
            client = get_db_client()
            if client is None:
                raise RuntimeError("DB client not initialized")
            await client.admin.command("ping")
            return JSONResponse(
                content={"ready": True, "database": "connected"},
            )
        except Exception:
            return JSONResponse(
                status_code=503,
                content={"ready": False, "database": "disconnected"},
            )

    return app


# ---------------------------------------------------------------------------
# Module-level app instance (used by uvicorn)
# ---------------------------------------------------------------------------
app = create_app()
