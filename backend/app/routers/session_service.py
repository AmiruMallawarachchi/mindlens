"""Session operations that coordinate session and related data storage."""

from __future__ import annotations

import datetime
import uuid

from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.routers.session_schemas import (
    SessionCreateRequest,
    SessionCreateResponse,
    SessionDeleteResponse,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def create_session_record(
    req: SessionCreateRequest | None, user_id: str, db: AsyncIOMotorDatabase
) -> SessionCreateResponse:
    """Reuse an empty active session or create a new session document."""
    now = datetime.datetime.now(datetime.UTC)
    if not (req and (req.title or req.context)):
        reusable = await db.sessions.find_one(
            {"user_id": user_id, "status": "active", "turns": []},
            sort=[("started_at", -1)],
        )
        if reusable:
            return SessionCreateResponse(
                session_id=reusable["session_id"],
                user_id=user_id,
                title=reusable.get("title"),
                started_at=reusable["started_at"],
                status="active",
            )

    session_id = str(uuid.uuid4())
    session_doc = {
        "session_id": session_id,
        "user_id": user_id,
        "title": req.title if req else None,
        "context": req.context if req else None,
        "started_at": now,
        "ended_at": None,
        "status": "active",
        "turns": [],
        "eos_timeline": [],
        "session_summary": "",
        "key_facts": [],
        "agents_used": [],
        "primary_modality": None,
        "check_in_scheduled": False,
        "pinned": False,
        "updated_at": now,
    }
    await db.sessions.insert_one(session_doc)
    logger.info("Session created: %s for user %s", session_id, user_id)
    return SessionCreateResponse(
        session_id=session_id,
        user_id=user_id,
        title=session_doc["title"],
        started_at=now,
        status="active",
    )


async def delete_session_data(
    session_id: str, user_id: str, db: AsyncIOMotorDatabase
) -> SessionDeleteResponse:
    """Hard-delete a session and all records scoped to that user/session."""
    session = await db.sessions.find_one({"session_id": session_id, "user_id": user_id})
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    scope = {"session_id": session_id, "user_id": user_id}
    session_result = await db.sessions.delete_one(scope)
    moods_result = await db.mood_logs.delete_many(scope)
    safety_result = await db.safety_events.delete_many(scope)

    deleted = {
        "sessions": session_result.deleted_count,
        "mood_logs": moods_result.deleted_count,
        "safety_events": safety_result.deleted_count,
    }
    logger.info("Session hard-deleted: %s for user %s (%s)", session_id, user_id, deleted)
    return SessionDeleteResponse(session_id=session_id, deleted=deleted)
