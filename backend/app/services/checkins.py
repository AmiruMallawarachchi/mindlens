"""Proactive check-ins: when to send one, what to say, and delivery.

A check-in is scheduled when a chat session ends and delivered the next time
the user opens chat. Scheduling is deliberately one document per session keyed
by ``(user_id, from_session)``: a reconnect refreshes the time and text without
re-arming a check-in that was already delivered.

This replaces the V1 ``CheckInScheduler`` + ``CheckInAgent`` pair, which were
registered but never dispatched by the V2 graph — every check-in ever sent
used a hardcoded generic line instead of the agent's own prompt.
"""

from __future__ import annotations

import datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.agents.groq_client import get_groq_client
from app.core.anonymizer import anonymize
from app.utils.logger import get_logger

logger = get_logger(__name__)

CHECKIN_FALLBACK_TEXT = (
    "Hey - I've been thinking about our last conversation. How are things now?"
)

_HISTORY_TURNS = 6
_LAST_TOPIC_CHARS = 100
_EXPIRY_DAYS = 7


def next_checkin_at(
    *,
    distress_level: float,
    preferred_time: str | None = None,
    now: datetime.datetime | None = None,
) -> datetime.datetime:
    """Return the next check-in time as a timezone-aware UTC datetime.

    Distress sets urgency: 4 hours at >= 0.7, 12 at >= 0.5, otherwise 24.
    For calmer turns, onboarding's morning/evening preference moves the
    check-in to 08:00 or 19:00 UTC instead of the distress-only offset.
    High distress deliberately ignores the preference and checks in sooner.
    """
    now = now or datetime.datetime.now(datetime.UTC)

    if distress_level >= 0.7:
        hours_until = 4
    elif distress_level >= 0.5:
        hours_until = 12
    else:
        hours_until = 24

    scheduled_at = now + datetime.timedelta(hours=hours_until)

    if preferred_time in ("morning", "evening") and distress_level < 0.7:
        target_hour = 8 if preferred_time == "morning" else 19
        candidate = scheduled_at.replace(
            hour=target_hour, minute=0, second=0, microsecond=0
        )
        if candidate <= now:
            candidate += datetime.timedelta(days=1)
        scheduled_at = candidate

    return scheduled_at


def _last_user_topic(session_history: list[dict[str, Any]]) -> str:
    """The most recent user message, anonymised and truncated for the prompt."""
    for turn in reversed(session_history):
        if turn.get("role") != "user":
            continue
        text = anonymize(str(turn.get("text", ""))).strip()
        if text:
            return text[:_LAST_TOPIC_CHARS]
    return "their recent concern"


async def generate_checkin_text(
    *,
    user_name: str,
    surface_emotion: str,
    distress_level: float,
    session_history: list[dict[str, Any]],
) -> str:
    """Generate a short, specific check-in. Falls back rather than raising —
    a failed model call must not lose the scheduling write."""
    name = user_name or "friend"
    last_topic = _last_user_topic(session_history)

    system = (
        f"You are MindLens - a warm, thoughtful wellbeing coach.\n"
        f"\nUSER CONTEXT:\n"
        f"- Name: {name}\n"
        f"- Last session emotion: {surface_emotion} (distress: {distress_level:.2f})\n"
        f"\nINSTRUCTIONS (follow ALL of them):\n"
        f"1. Write a warm, SHORT (2-3 sentences) proactive check-in message for {name}.\n"
        f"2. Recall something specific from the last session (e.g., a person they mentioned, an event, a worry).\n"
        f"3. Ask how they're doing now.\n"
        f"4. Do NOT start with 'How are you?' - be specific instead.\n"
        f"5. Sound like a friend checking in, not a bot.\n"
        f"6. NEVER diagnose.\n"
        f"\nRespond ONLY with the check-in message. No quotes, no meta-commentary.\n"
    )
    user = (
        f"Generate a check-in message for {name}.\n"
        f"Last session summary: feeling {surface_emotion} about {last_topic}.\n"
        f"Distress level at end of last session: {distress_level:.2f}."
    )

    try:
        result = await get_groq_client().chat(
            system_prompt=system,
            user_prompt=user,
            model_tier="8B",
            max_tokens=80,
            temperature=0.75,
        )
        text = result.text.strip()
        if text:
            return text
    except Exception:
        logger.exception("Check-in text generation failed for %s", name)
    return CHECKIN_FALLBACK_TEXT


async def schedule_checkin(
    db: AsyncIOMotorDatabase,
    *,
    session_id: str,
    user_id: str,
    user_name: str,
) -> datetime.datetime | None:
    """Schedule one check-in for a finished session.

    Reads the last assistant turn's EOS snapshot from the session rather than
    being handed pipeline state, so it can run from the WebSocket disconnect
    handler after the graph has already returned. Returns the scheduled time,
    or ``None`` when there is nothing to follow up on or the user's memory
    depth is "nothing" (a check-in about the last session is memory recall).
    """
    session = await db.sessions.find_one(
        {"session_id": session_id, "user_id": user_id},
        {"turns": {"$slice": -_HISTORY_TURNS}},
    )
    if not session:
        return None

    history = session.get("turns", [])
    last_assistant = next(
        (turn for turn in reversed(history) if turn.get("role") == "assistant"),
        None,
    )
    if not last_assistant:
        return None

    memory = await db.user_memory.find_one({"user_id": user_id}) or {}
    preferences = memory.get("preferences") or {}
    if preferences.get("memory_depth") == "nothing":
        return None

    eos = last_assistant.get("eos_snapshot") or {}
    distress_level = float(eos.get("distress_level") or 0.0)
    surface_emotion = str(eos.get("surface_emotion") or "unknown")

    scheduled_at = next_checkin_at(
        distress_level=distress_level,
        preferred_time=preferences.get("checkin_preferred_time"),
    )
    text = await generate_checkin_text(
        user_name=user_name,
        surface_emotion=surface_emotion,
        distress_level=distress_level,
        session_history=history,
    )

    now = datetime.datetime.now(datetime.UTC)
    await db.pending_checkins.update_one(
        {"user_id": user_id, "from_session": session_id},
        {
            "$set": {
                "scheduled_at": scheduled_at,
                "expires_at": scheduled_at + datetime.timedelta(days=_EXPIRY_DAYS),
                "text": text,
                "updated_at": now,
            },
            "$setOnInsert": {
                "user_id": user_id,
                "from_session": session_id,
                "delivered": False,
                "created_at": now,
            },
        },
        upsert=True,
    )
    return scheduled_at


async def send_pending_checkin(
    db: AsyncIOMotorDatabase,
    user_id: str,
    conn_manager: Any,
) -> None:
    """Deliver one due, undelivered check-in when the user opens chat."""
    checkin = await db.pending_checkins.find_one(
        {
            "user_id": user_id,
            "delivered": False,
            "scheduled_at": {"$lte": datetime.datetime.now(datetime.UTC)},
        }
    )
    if not checkin:
        return

    await conn_manager.send_checkin(
        user_id=user_id,
        text=checkin.get("text", CHECKIN_FALLBACK_TEXT),
        from_session=checkin.get("from_session", ""),
    )
    await db.pending_checkins.update_one(
        {"_id": checkin["_id"]},
        {
            "$set": {
                "delivered": True,
                "delivered_at": datetime.datetime.now(datetime.UTC),
            }
        },
    )
