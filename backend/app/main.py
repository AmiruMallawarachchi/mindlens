"""MindLens FastAPI application factory."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncGenerator, Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.config import settings
from app.core.connection_manager import get_connection_manager
from app.db import connect_db, disconnect_db, get_db_client
from app.middleware import MindLensAuthMiddleware
from app.models.loader import model_manager
from app.rag.ingest import ingest_documents
from app.rag.vector_store import get_vector_store
from app.routers import (
    auth_router,
    chat_router,
    dashboard_router,
    memory_router,
    onboarding_router,
    session_router,
    system_router,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Connect required dependencies and optionally warm model state."""
    logger.info("MindLens backend starting up")
    await connect_db()
    if settings.preload_models:
        await model_manager.warmup_all()
        logger.info("Configured models preloaded")
    if settings.preload_rag:
        chunk_count = await asyncio.to_thread(ingest_documents)
        if chunk_count == 0:
            raise RuntimeError("RAG preload produced no knowledge chunks")
        logger.info("RAG knowledge ready: %d chunks", chunk_count)
    yield
    logger.info("MindLens backend shutting down")
    await get_connection_manager().shutdown()
    await disconnect_db()


def create_app() -> FastAPI:
    """Build and configure the API application."""
    application = FastAPI(
        title="MindLens API",
        description="Multi-agent AI system for personalized mental health support",
        version="0.4.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "X-Request-ID"],
    )
    application.add_middleware(MindLensAuthMiddleware)

    application.include_router(auth_router, prefix="/api/v1/auth", tags=["Authentication"])
    application.include_router(session_router, prefix="/api/v1/sessions", tags=["Session"])
    application.include_router(chat_router, prefix="/ws", tags=["WebSocket"])
    application.include_router(
        dashboard_router, prefix="/api/v1/dashboard", tags=["Dashboard"]
    )
    application.include_router(
        onboarding_router, prefix="/api/v1/onboarding", tags=["Onboarding"]
    )
    application.include_router(memory_router, prefix="/api/v1/memory", tags=["Memory"])
    application.include_router(system_router, prefix="/api/v1/admin", tags=["Admin"])

    @application.middleware("http")
    async def security_headers(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cache-Control"] = "no-store"
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response

    @application.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "request_id": request.state.request_id},
        )

    @application.get("/health", tags=["System"])
    async def health_check() -> dict[str, str]:
        return {
            "status": "ok",
            "version": "0.4.0",
            "release": settings.render_git_commit[:12],
        }

    @application.get("/ready", tags=["System"])
    async def readiness_check() -> JSONResponse:
        try:
            client = get_db_client()
            if client is None:
                raise RuntimeError("Database client not initialized")
            await client.admin.command("ping")
            models = model_manager.health_status()
            model_ready = not settings.preload_models or all(
                item["status"] == "ready" for item in models.values()
            )
            rag_status: dict[str, object] = {"status": "lazy"}
            if settings.preload_rag:
                rag_count = await asyncio.to_thread(get_vector_store().count)
                rag_status = {"status": "ready" if rag_count else "empty", "chunks": rag_count}
                model_ready = model_ready and rag_count > 0
            return JSONResponse(
                status_code=200 if model_ready else 503,
                content={
                    "ready": model_ready,
                    "database": "connected",
                    "models": models,
                    "rag": rag_status,
                },
            )
        except Exception:
            return JSONResponse(
                status_code=503,
                content={"ready": False, "database": "disconnected"},
            )

    return application


app = create_app()
