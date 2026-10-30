"""Post-authentication WebSocket message processing."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import WebSocket
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.agents.streaming import stream_pipeline_result
from app.config import settings
from app.middleware.auth import get_rate_limit_store
from app.utils.logger import get_logger

from .checkins import _save_pending_checkin
from .memory import _save_extracted_memory
from .persistence import (
    _load_session_history,
    _save_assistant_turn,
    _save_mood_log,
    _save_safety_event,
    _save_user_turn,
)

logger = get_logger("app.routers.chat")
WS_TIMEOUT = settings.WS_MESSAGE_TIMEOUT_SECONDS


async def run_chat_message_loop(
    websocket: WebSocket,
    db: AsyncIOMotorDatabase,
    session_id: str,
    user_id: str,
    user_name: str,
    conn_manager: Any,
    orchestrator: Any,
) -> None:
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

        # Build session history (last 10 turns from DB) before this turn
        # is written, so it stays prior-context only.
        session_history = await _load_session_history(db, session_id, user_id)
        user_memory = await db.user_memory.find_one({"user_id": user_id})

        # Persist what the user actually typed *before* the pipeline
        # runs. A pipeline crash, a starved process, or a streaming
        # failure below must never cost the user their own message —
        # previously the write only happened after both succeeded, so
        # any failure silently dropped it from the transcript forever.
        await _save_user_turn(db, session_id, user_id, user_text)

        # Run full pipeline
        try:
            # Emitted as each stage genuinely finishes, so the trail
            # fills in a step at a time rather than appearing complete.
            async def _on_stage(stage: str, detail: str) -> None:
                await conn_manager.send_stage_update(user_id, stage, detail)

            result = await orchestrator.run_full_pipeline(
                user_text=user_text,
                user_name=user_name,
                session_history=session_history,
                rag_chunks=None,
                user_id=user_id,
                memory=user_memory,
                on_stage=_on_stage,
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
            # The user's turn is already saved above — only the reply is
            # missing, and that's what the error frame communicates.
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

        # Persist the assistant's reply now that it actually exists.
        await _save_assistant_turn(db, session_id, user_id, result)
        await _save_mood_log(db, session_id, user_id, result)
        await _save_safety_event(db, session_id, user_id, user_text, result)
        await _save_pending_checkin(
            db, session_id, user_id, user_name, session_history, result
        )
        # Best-effort background enrichment, not this turn's content: the
        # reply is already streamed and saved above, so a failure here
        # should cost this turn's personality/memory update, not the
        # whole connection. Previously bare, these were the only two
        # post-stream writes not already isolated like the pipeline and
        # streaming calls above — an unhandled exception (including the
        # DuplicateKeyError race noted below) fell through to the outer
        # handler and silently disconnected the user over a background save.
        try:
            await _save_extracted_memory(db, user_id, result)
        except Exception:
            logger.exception(
                "Background memory update failed for user %s", user_id
            )

