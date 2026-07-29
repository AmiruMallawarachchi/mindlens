"""
MindLens WebSocket Chat Router
==============================
Real-time streaming endpoint: /ws/chat/{session_id}

Flow:
  1. Client opens WebSocket with JWT in subprotocol header
  2. Server validates JWT, checks session ownership
  3. Enforces single connection per user
  4. Message loop with 5-minute inactivity timeout
  5. Each message → Orchestrator → Streaming → WebSocket

Security:
  - JWT in header (not URL params)
  - Session ownership enforced (user can only access their own sessions)
  - Single connection per user (old connection closed)
  - 5-minute timeout on inactivity
  - All PII stripped before model calls
"""

from __future__ import annotations

import asyncio
import datetime
import hashlib
from typing import Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from jwt.exceptions import PyJWTError as JWTError
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.agents.base_agent import AgentContext
from app.agents.checkin_agent import CheckInAgent
from app.agents.orchestrator import Orchestrator
from app.agents.streaming import stream_pipeline_result
from app.config import settings
from app.core.connection_manager import get_connection_manager
from app.core.emotional_os import EmotionalOperatingState
from app.db import document_id_filter, get_db
from app.middleware.auth import get_rate_limit_store, verify_access_token
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()

# Message timeout (seconds)
WS_TIMEOUT = settings.WS_MESSAGE_TIMEOUT_SECONDS


@router.websocket("/chat/{session_id}")
async def websocket_chat(
    websocket: WebSocket,
    session_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    WebSocket endpoint for real-time therapy chat.

    JWT must be supplied through the secure cookie, server Authorization header,
    or the `mindlens.jwt.<token>` WebSocket subprotocol. URL query tokens are
    deliberately rejected to keep credentials out of access logs.
    Full path: /ws/chat/{session_id}

    """
    # -------------------------------------------------------------------
    # 1. Extract and validate JWT
    # -------------------------------------------------------------------
    if not _origin_allowed(websocket):
        await websocket.close(code=4003, reason="Origin not allowed")
        return

    token, selected_subprotocol = _extract_token(websocket)
    if not token:
        logger.warning("WebSocket connection rejected: no token (session=%s)", session_id)
        await websocket.close(code=4001, reason="Missing authorization token")
        return

    try:
        jwt_user = verify_access_token(token)
    except JWTError as exc:
        logger.warning("WebSocket connection rejected: invalid token (%s)", exc)
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    user_id = jwt_user.id

    # -------------------------------------------------------------------
    # 2. Verify session ownership
    # -------------------------------------------------------------------
    session = await db.sessions.find_one({
        "session_id": session_id,
        "user_id": user_id,
    })
    if not session:
        logger.warning(
            "WebSocket connection rejected: session not found or not owned "
            "(session=%s, user=%s)", session_id, user_id
        )
        await websocket.close(code=4003, reason="Forbidden: session not found")
        return

    # -------------------------------------------------------------------
    # 3. ConnectionManager: accept and enforce single connection
    # -------------------------------------------------------------------
    conn_manager = get_connection_manager()
    connected = await conn_manager.connect(
        websocket, user_id, session_id, subprotocol=selected_subprotocol
    )
    if not connected:
        logger.warning("WebSocket connection failed for user %s", user_id)
        await websocket.close(code=1013, reason="Try again later")
        return

    # Initialize orchestrator
    orchestrator = Orchestrator()

    # Load user profile for personalization
    user = await db.users.find_one(document_id_filter(user_id))
    user_name = user.get("nickname", user.get("name", "friend")) if user else "friend"

    # Send welcome / check-in if pending
    await _send_pending_checkin(db, user_id, conn_manager)

    logger.info(
        "WebSocket chat started: user=%s session=%s",
        user_id, session_id,
    )

    # -------------------------------------------------------------------
    # 4. Message loop
    # -------------------------------------------------------------------
    try:
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=WS_TIMEOUT,
                )
            except TimeoutError:
                logger.info("WebSocket timeout for user %s", user_id)
                await websocket.close(code=1000, reason="Session timeout")
                break

            # Validate message structure
            msg_type = data.get("type")
            if msg_type != "message":
                # Handle ping/pong, acks, etc.
                if msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
                continue

            user_text = data.get("text", "").strip()
            if not user_text:
                continue

            allowed = await get_rate_limit_store().check_user(
                user_id, settings.RATE_LIMIT_PER_USER_HOUR
            )
            if not allowed:
                await conn_manager.send_to_user(
                    user_id,
                    {"type": "error", "detail": "Hourly message limit exceeded"},
                )
                continue

            # Message length cap (2000 chars per SYSTEM.md §22.3)
            if len(user_text) > settings.ws_max_message_chars:
                await conn_manager.send_to_user(
                    user_id,
                    {
                        "type": "error",
                        "detail": (
                            "Message too long "
                            f"(max {settings.ws_max_message_chars} characters)"
                        ),
                    },
                )
                continue

            # Build session history (last 10 turns from DB)
            session_history = await _load_session_history(db, session_id, user_id)
            user_memory = await db.user_memory.find_one({"user_id": user_id})

            # Run full pipeline
            try:
                result = await orchestrator.run_full_pipeline(
                    user_text=user_text,
                    user_name=user_name,
                    session_history=session_history,
                    rag_chunks=None,
                    user_id=user_id,
                    memory=user_memory,
                )
            except Exception as exc:
                logger.exception("Pipeline error for user %s: %s", user_id, exc)
                await conn_manager.send_to_user(
                    user_id,
                    {
                        "type": "error",
                        "detail": "I'm having trouble right now. Please try again in a moment.",
                    },
                )
                continue

            # Stream result to WebSocket
            try:
                await stream_pipeline_result(
                    user_id=user_id,
                    session_id=session_id,
                    pipeline_result=result,
                    conn_manager=conn_manager,
                    enable_streaming=True,
                )
            except Exception as exc:
                logger.exception("Streaming error for user %s: %s", user_id, exc)
                # Fallback: send non-streaming error
                await conn_manager.send_to_user(
                    user_id,
                    {
                        "type": "error",
                        "detail": "Failed to send response. Please reconnect.",
                    },
                )
                continue

            # Persist turn to session
            await _save_turn(db, session_id, user_id, user_text, result)
            await _save_mood_log(db, session_id, user_id, result)
            await _save_safety_event(db, session_id, user_id, user_text, result)
            await _save_pending_checkin(
                db, session_id, user_id, user_name, session_history, result
            )

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: user=%s session=%s", user_id, session_id)
    except Exception:
        logger.exception("WebSocket loop error: user=%s session=%s", user_id, session_id)
    finally:
        # Cleanup
        await conn_manager.disconnect(user_id)
        await _save_session_on_disconnect(db, session_id, user_id)
        logger.info("WebSocket cleanup complete: user=%s", user_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_token(websocket: WebSocket) -> tuple[str | None, str | None]:
    """Extract JWT from a cookie, server client header, or WebSocket subprotocol."""
    cookie_token = websocket.cookies.get("access_token")
    if cookie_token:
        return cookie_token, None
    if websocket.headers.get("authorization"):
        auth = websocket.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:], None
    offered = websocket.headers.get("sec-websocket-protocol", "")
    for protocol in (item.strip() for item in offered.split(",")):
        if protocol.startswith("mindlens.jwt."):
            return protocol.removeprefix("mindlens.jwt."), protocol
    return None, None


def _origin_allowed(websocket: WebSocket) -> bool:
    """Reject browser WebSocket handshakes from untrusted origins."""
    origin = websocket.headers.get("origin")
    return not origin or origin in settings.cors_origins


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


async def _save_turn(
    db: AsyncIOMotorDatabase,
    session_id: str,
    user_id: str,
    user_text: str,
    result: dict[str, Any],
) -> None:
    """Append the turn to the session document."""
    now = datetime.datetime.now(datetime.UTC)
    turn_doc = {
        "role": "user",
        "text": user_text,
        "timestamp": now,
    }
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
                "turns": {"$each": [turn_doc, assistant_doc]},
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


# Generic fallback only — never the primary path. SYSTEM.md §5.12 explicitly
# forbids opening a check-in with "How are you?"; this is deliberately
# specific-but-safe instead, used only if the model call itself fails.
_CHECKIN_FALLBACK_TEXT = (
    "Hey — I've been thinking about our last conversation. How are things now?"
)


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
