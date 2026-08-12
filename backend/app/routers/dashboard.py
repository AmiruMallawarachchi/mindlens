"""Authenticated mood and progress dashboard endpoints."""

from __future__ import annotations

import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.agents.base_agent import AgentContext
from app.agents.progress_agent import ProgressAgent
from app.core.emotional_os import AgeGroup, EmotionalOperatingState
from app.db import get_db
from app.middleware.auth import require_user
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()

# progress_agent.py's own docstring: "Trigger: Every 7 sessions OR user
# clicks Progress". design.md §4.2 gates the insight card on >= 7 sessions.
MIN_SESSIONS_FOR_INSIGHT = 7
REGENERATE_EVERY_N_SESSIONS = 7


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


@router.get("/insight")
async def get_progress_insight(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """
    Weekly progress insight — design.md §4.2's "Weekly insight card (only
    with >= 7 sessions)".

    ProgressAgent (SYSTEM.md §5.13) has always existed and could run inside
    a chat turn (orchestrator._select_agents every 5th turn), but nothing
    exposed it as a REST endpoint, so the Progress tab could never show more
    than the honest "N more sessions to unlock" placeholder. This is that
    endpoint.

    Regenerates at most once every 7 sessions — matching the agent's own
    "every 7 sessions" cadence — rather than spending an LLM call on every
    dashboard visit; between regenerations the cached insight is returned.
    """
    user_id = str(current_user["_id"])
    session_count = await db.sessions.count_documents({"user_id": user_id})

    if session_count < MIN_SESSIONS_FOR_INSIGHT:
        return {
            "available": False,
            "session_count": session_count,
            "sessions_needed": MIN_SESSIONS_FOR_INSIGHT - session_count,
        }

    cached = await db.progress_insights.find_one({"user_id": user_id})
    if cached and (
        session_count - cached.get("session_count_at_generation", 0)
        < REGENERATE_EVERY_N_SESSIONS
    ):
        return {
            "available": True,
            "insight": cached["insight"],
            "generated_at": cached["generated_at"],
            "session_count": session_count,
        }

    user = await db.users.find_one({"_id": current_user["_id"]}) or current_user
    user_name = user.get("nickname") or user.get("name") or "friend"
    age_group_raw = user.get("age_group", "adult")

    recent_moods = await (
        db.mood_logs.find({"user_id": user_id}, {"_id": 0})
        .sort("timestamp", -1)
        .limit(7)
        .to_list(length=7)
    )

    avg_distress = (
        sum(m.get("distress_level") or 0.0 for m in recent_moods) / len(recent_moods)
        if recent_moods
        else 0.4
    )
    latest_emotion = recent_moods[0].get("surface_emotion") if recent_moods else None

    eos = EmotionalOperatingState(
        surface_emotion=latest_emotion or "neutral",
        distress_level=round(avg_distress, 3),
        age_group=AgeGroup(age_group_raw) if age_group_raw in ("teen", "adult") else AgeGroup.ADULT,
    )
    # progress_agent._build_user_prompt_v3 reads turn.get("emotion") — shape
    # the mood log history to match rather than changing the agent's contract.
    session_history = [
        {"emotion": m.get("surface_emotion", "unknown")} for m in reversed(recent_moods)
    ]
    ctx = AgentContext(
        eos=eos,
        user_text="",
        user_name=user_name,
        session_history=session_history,
    )

    try:
        output = await ProgressAgent().run(ctx)
    except Exception:
        logger.exception("Progress insight generation failed for user %s", user_id)
        return {
            "available": True,
            "insight": None,
            "session_count": session_count,
            "error": "Could not generate an insight right now. Try again shortly.",
        }

    now = datetime.datetime.now(datetime.UTC)
    await db.progress_insights.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "insight": output.text,
                "generated_at": now,
                "session_count_at_generation": session_count,
            }
        },
        upsert=True,
    )

    return {
        "available": True,
        "insight": output.text,
        "generated_at": now,
        "session_count": session_count,
    }
