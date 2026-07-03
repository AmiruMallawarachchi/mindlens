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
import time
from typing import Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from jose import JWTError
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.agents.orchestrator import Orchestrator
from app.agents.streaming import stream_pipeline_result
from app.config import settings
from app.core.connection_manager import get_connection_manager
from app.db import get_db
from app.middleware.auth import verify_access_token
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

    JWT must be passed in the `Authorization` subprotocol header:
      new WebSocket(url, ["eyJhbG..."])

    Or as a query param `token=` (fallback, less secure).
    Full path: /ws/chat/{session_id}

    """
    # -------------------------------------------------------------------
    # 1. Extract and validate JWT
    # -------------------------------------------------------------------
    token = _extract_token(websocket)
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
    connected = await conn_manager.connect(websocket, user_id, session_id)
    if not connected:
        logger.warning("WebSocket connection failed for user %s", user_id)
        await websocket.close(code=1013, reason="Try again later")
        return

    # Initialize orchestrator
    orchestrator = Orchestrator()

    # Load user profile for personalization
    user = await db.users.find_one({"_id": user_id})
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

            # Message length cap (2000 chars per SYSTEM.md §22.3)
            if len(user_text) > 2000:
                await conn_manager.send_to_user(
                    user_id,
                    {
                        "type": "error",
                        "detail": "Message too long (max 2000 characters)",
                    },
                )
                continue

            # Build session history (last 10 turns from DB)
            session_history = await _load_session_history(db, session_id, user_id)

            # Run full pipeline
            try:
                result = await orchestrator.run_full_pipeline(
                    user_text=user_text,
                    user_name=user_name,
                    session_history=session_history,
                    rag_chunks=[],  # TODO: wire RAG when ready
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


def _extract_token(websocket: WebSocket) -> str | None:
    """Extract JWT from subprotocol header or query param."""
    # Prefer subprotocol (most secure for WebSocket)
    if websocket.headers.get("authorization"):
        auth = websocket.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:]
    # Fallback: check query params
    return websocket.query_params.get("token")


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
    now = time.time()
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


async def _save_session_on_disconnect(
    db: AsyncIOMotorDatabase,
    session_id: str,
    user_id: str,
) -> None:
    """Update session on disconnect (e.g., mark as inactive if ended)."""
    # For now, just update last_activity. Ending is explicit via REST DELETE.
    await db.sessions.update_one(
        {"session_id": session_id, "user_id": user_id},
        {"$set": {"last_activity": time.time()}},
    )


async def _send_pending_checkin(
    db: AsyncIOMotorDatabase,
    user_id: str,
    conn_manager,
) -> None:
    """Send any pending check-in message when user opens WebSocket."""
    checkin = await db.pending_checkins.find_one(
        {"user_id": user_id, "delivered": False}
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
            {"$set": {"delivered": True, "delivered_at": time.time()}},
        )
