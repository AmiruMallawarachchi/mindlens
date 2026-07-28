"""Authenticated operational endpoints for administrators."""

from __future__ import annotations

import datetime
from typing import Any

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import settings
from app.db import get_db
from app.middleware.auth import require_admin
from app.models.loader import model_manager

router = APIRouter()


@router.get("/system", summary="Get backend operational status")
async def system_status(
    db: AsyncIOMotorDatabase = Depends(get_db),
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    await db.client.admin.command("ping")
    return {
        "status": "ok",
        "environment": settings.app_env,
        "release": settings.render_git_commit[:12],
        "database": "connected",
        "models": model_manager.health_status(),
        "timestamp": datetime.datetime.now(datetime.UTC),
    }


@router.get("/models", summary="Get model registry health")
async def model_status(
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    return {"models": model_manager.health_status()}
