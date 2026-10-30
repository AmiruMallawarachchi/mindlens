"""MindLens FastAPI application factory."""

from __future__ import annotations

import contextlib
from collections.abc import AsyncGenerator, Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.config import settings
from app.core.connection_manager import get_connection_manager
from app.db import connect_db, disconnect_db, get_db_client
from app.middleware import MindLensAuthMiddleware
from app.routers import (
    account_router,
    auth_router,
    chat_router,
    dashboard_router,
    journal_router,
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
    logger.info("V2 uses hosted inference and hosted retrieval")
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
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-CSRF-Token",
            "X-Request-ID",
            # Not a real auth/content header — it exists only so the
            # frontend can bypass ngrok's free-tier browser interstitial
            # (see frontend/src/lib/api.ts). Harmless against any backend
            # host that isn't ngrok; without it in this allowlist, the
            # browser's CORS preflight is rejected with 400 before the
            # real request is ever sent.
            "ngrok-skip-browser-warning",
        ],
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
    application.include_router(account_router, prefix="/api/v1/account", tags=["Account"])
    application.include_router(journal_router, prefix="/api/v1/journal", tags=["Journal"])
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
            # A configured key is not enough: a deployment running with
            # USE_OPENAI_STUBS=true would answer every turn from canned text
            # and still look healthy. Readiness must reflect real inference.
            model_ready = bool(settings.groq_api_key) and not settings.use_openai_stubs
            if model_ready:
                inference_status = "configured"
            elif settings.use_openai_stubs:
                inference_status = "stub_mode"
            else:
                inference_status = "missing_key"
            rag_status: dict[str, object] = {
                "status": "configured" if settings.pinecone_api_key and settings.pinecone_index_name else "not_configured",
                "provider": "pinecone",
                # Retrieval is fail-soft: the graph answers without it, so a
                # missing or unreachable index must not fail readiness. It is
                # reported as configuration, not reachability, on purpose.
                "mode": "fail_soft",
            }
            return JSONResponse(
                status_code=200 if model_ready else 503,
                content={
                    "ready": model_ready,
                    "database": "connected",
                    "inference": {
                        "provider": "groq",
                        "status": inference_status,
                        "stub_mode": settings.use_openai_stubs,
                    },
                    "rag": rag_status,
                    "observability": {
                        "provider": "langfuse",
                        "enabled": settings.langfuse_enabled,
                        "configured": bool(
                            settings.langfuse_public_key
                            and settings.langfuse_secret_key
                        ),
                    },
                },
            )
        except Exception:
            return JSONResponse(
                status_code=503,
                content={"ready": False, "database": "disconnected"},
            )

    return application


app = create_app()
