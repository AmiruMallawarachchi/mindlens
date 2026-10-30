"""Pending check-in delivery and scheduling helpers."""

from __future__ import annotations

import datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.agents.base_agent import AgentContext
from app.agents.checkin_agent import CheckInAgent
from app.core.emotional_os import EmotionalOperatingState
from app.utils.logger import get_logger

logger = get_logger("app.routers.chat")

_CHECKIN_FALLBACK_TEXT = (
    "Hey - I've been thinking about our last conversation. How are things now?"
)


async def _send_pending_checkin(
    db: AsyncIOMotorDatabase,
    user_id: str,
    conn_manager,
) -> None:
    """Send any pending check-in message when user opens WebSocket."""
    checkin = await db.pending_checkins.find_one(
        {
            "user_id": user_id,
            "delivered": False,
            "scheduled_at": {"$lte": datetime.datetime.now(datetime.UTC)},
        }
    )
    if checkin:
        await conn_manager.send_checkin(
            user_id=user_id,
            text=checkin.get("text", "Hey — how are you doing today?"),
            from_session=checkin.get("from_session", ""),
        )
        # Mark as delivered
        await db.pending_checkins.update_one(
            {"_id": checkin["_id"]},
            {
                "$set": {
                    "delivered": True,
                    "delivered_at": datetime.datetime.now(datetime.UTC),
                }
            },
        )


async def _save_pending_checkin(
    db: AsyncIOMotorDatabase,
    session_id: str,
    user_id: str,
    user_name: str,
    session_history: list[dict[str, Any]],
    result: dict[str, Any],
) -> None:
    """
    Persist scheduler-agent output so it survives process restarts.

    The text comes from CheckInAgent (SYSTEM.md §5.12: recall something
    specific, never open with "How are you?"). CheckInAgent was registered
    in the orchestrator's agent list but never included in
    Orchestrator._select_agents — only checkin_scheduler (which computes
    *when* to check in) ran, so every proactive check-in ever sent used the
    hardcoded line here, which was the exact generic opener the agent's own
    prompt forbids. Generating it here, rather than by adding "checkin" to
    the orchestrator's turn-agents, keeps it out of the current turn's
    visible reply — this message is for a *future* check-in, not this turn.
    """
    for output in result.get("agent_outputs", []):
        metadata = output.get("metadata", {})
        if metadata.get("action") != "schedule_checkin":
            continue
        scheduled_at = datetime.datetime.fromisoformat(metadata["scheduled_at"])
        if scheduled_at.tzinfo is None:
            scheduled_at = scheduled_at.replace(tzinfo=datetime.UTC)

        checkin_text = await _generate_checkin_text(
            eos=result.get("eos", {}),
            user_name=user_name,
            session_history=session_history,
        )

        await db.pending_checkins.update_one(
            {
                "user_id": user_id,
                "from_session": session_id,
                "delivered": False,
            },
            {
                "$set": {
                    "scheduled_at": scheduled_at,
                    "expires_at": scheduled_at + datetime.timedelta(days=7),
                    "text": checkin_text,
                },
                "$setOnInsert": {
                    "user_id": user_id,
                    "from_session": session_id,
                    "delivered": False,
                    "created_at": datetime.datetime.now(datetime.UTC),
                },
            },
            upsert=True,
        )
        break


async def _generate_checkin_text(
    eos: dict[str, Any],
    user_name: str,
    session_history: list[dict[str, Any]],
) -> str:
    """Best-effort personalised check-in text. Falls back to a plain but
    still non-generic line if the model call fails, rather than raising and
    losing the whole scheduling write."""
    try:
        ctx = AgentContext(
            eos=EmotionalOperatingState(**eos),
            user_text="",
            user_name=user_name,
            session_history=session_history,
        )
        output = await CheckInAgent().run(ctx)
        if output.text:
            return output.text
    except Exception:
        logger.exception("Check-in text generation failed for user %s", user_name)
    return _CHECKIN_FALLBACK_TEXT

