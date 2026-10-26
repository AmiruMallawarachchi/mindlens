"""Session, mood, and safety event persistence for WebSocket chat."""

from __future__ import annotations

import datetime
import hashlib
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase


async def _load_session_history(
    db: AsyncIOMotorDatabase,
    session_id: str,
    user_id: str,
) -> list[dict[str, Any]]:
    """Load last 10 turns from session for context window."""
    session = await db.sessions.find_one(
        {"session_id": session_id, "user_id": user_id},
        {"turns": {"$slice": -10}},
    )
    if not session:
        return []
    return session.get("turns", [])[-10:]


async def _save_user_turn(
    db: AsyncIOMotorDatabase,
    session_id: str,
    user_id: str,
    user_text: str,
) -> None:
    """Append the user's turn immediately, before the pipeline runs.

    See the call site in the message loop: this exists specifically so a
    pipeline or streaming failure afterward loses only the reply, never
    what the user actually typed.
    """
    now = datetime.datetime.now(datetime.UTC)
    await db.sessions.update_one(
        {"session_id": session_id, "user_id": user_id},
        {
            "$push": {"turns": {"role": "user", "text": user_text, "timestamp": now}},
            "$set": {"updated_at": now},
        },
    )


async def _save_assistant_turn(
    db: AsyncIOMotorDatabase,
    session_id: str,
    user_id: str,
    result: dict[str, Any],
) -> None:
    """Append the assistant's reply once the pipeline has actually produced one."""
    now = datetime.datetime.now(datetime.UTC)
    assistant_doc = {
        "role": "assistant",
        "text": result.get("assembled_text", ""),
        "agents_used": result.get("agents", []),
        "eos_snapshot": result.get("eos", {}),
        "crisis_flag": result.get("crisis_flag", False),
        "timestamp": now,
    }

    await db.sessions.update_one(
        {"session_id": session_id, "user_id": user_id},
        {
            "$push": {
                "turns": assistant_doc,
                "eos_timeline": result.get("eos", {}),
            },
            "$addToSet": {"agents_used": {"$each": result.get("agents", [])}},
            "$set": {
                "primary_modality": result.get("eos", {}).get("modality"),
                "updated_at": now,
            },
        },
    )


async def _save_mood_log(
    db: AsyncIOMotorDatabase,
    session_id: str,
    user_id: str,
    result: dict[str, Any],
) -> None:
    """
    Record one mood_logs entry per turn from the EOS snapshot.

    dashboard.py's /mood and /summary endpoints read this collection, but
    nothing wrote to it — the Progress tab had a real API contract backed by
    an always-empty collection. Crisis turns are skipped: crisis_flag turns
    carry a template response with no real EOS inference behind it (the
    orchestrator short-circuits before model inference), so there's no
    genuine emotion reading to log.
    """
    if result.get("crisis_flag"):
        return
    eos = result.get("eos", {})
    await db.mood_logs.insert_one(
        {
            "user_id": user_id,
            "session_id": session_id,
            "timestamp": datetime.datetime.now(datetime.UTC),
            "surface_emotion": eos.get("surface_emotion"),
            "core_emotion": eos.get("core_emotion"),
            "distress_level": eos.get("distress_level"),
            "valence": eos.get("valence"),
            "modality": eos.get("modality"),
        }
    )


async def _save_session_on_disconnect(
    db: AsyncIOMotorDatabase,
    session_id: str,
    user_id: str,
) -> None:
    """Update session on disconnect (e.g., mark as inactive if ended)."""
    # For now, just update last_activity. Ending is explicit via REST DELETE.
    await db.sessions.update_one(
        {"session_id": session_id, "user_id": user_id},
        {"$set": {"last_activity": datetime.datetime.now(datetime.UTC)}},
    )


async def _save_safety_event(
    db: AsyncIOMotorDatabase,
    session_id: str,
    user_id: str,
    user_text: str,
    result: dict[str, Any],
) -> None:
    """Persist privacy-preserving crisis audit metadata."""
    if not result.get("crisis_flag"):
        return
    await db.safety_events.insert_one(
        {
            "user_id": user_id,
            "session_id": session_id,
            "message_sha256": hashlib.sha256(user_text.encode("utf-8")).hexdigest(),
            "safety": result.get("safety", {}),
            "timestamp": datetime.datetime.now(datetime.UTC),
        }
    )

