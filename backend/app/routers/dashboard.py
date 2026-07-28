"""Authenticated mood and progress dashboard endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db import get_db
from app.middleware.auth import require_user

router = APIRouter()


@router.get("/mood")
async def get_mood_logs(
    limit: int = Query(default=30, ge=1, le=90),
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_user),
) -> dict[str, list[dict[str, Any]]]:
    user_id = str(current_user["_id"])
    cursor = (
        db.mood_logs.find({"user_id": user_id}, {"_id": 0})
        .sort("timestamp", -1)
        .limit(limit)
    )
    return {"moods": await cursor.to_list(length=limit)}


@router.get("/summary")
async def get_dashboard_summary(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    user_id = str(current_user["_id"])
    session_count = await db.sessions.count_documents({"user_id": user_id})
    memory = await db.user_memory.find_one({"user_id": user_id}, {"_id": 0})
    latest_moods = await (
        db.mood_logs.find({"user_id": user_id}, {"_id": 0})
        .sort("timestamp", -1)
        .limit(7)
        .to_list(length=7)
    )
    return {
        "session_count": session_count,
        "latest_moods": latest_moods,
        "memory_enabled": memory is not None,
    }
