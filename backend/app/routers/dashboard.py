# backend/app/routers/dashboard.py
"""Dashboard router — mood logs, progress data."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/mood")
async def get_mood_logs() -> dict[str, list]:
    return {"moods": []}