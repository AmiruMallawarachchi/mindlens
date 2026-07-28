"""
MindLens Session Router (REST)
==============================
Create, list, and end therapy sessions.

- POST /api/v1/sessions          → create new session
- GET  /api/v1/sessions          → list user's sessions
- GET  /api/v1/sessions/{id}     → get session transcript
- DELETE /api/v1/sessions/{id}   → end / soft-delete session

All endpoints enforce user_id isolation — users can only see their own sessions.
"""

from __future__ import annotations

import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.db import get_db
from app.middleware.auth import require_user
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


# --- Pydantic Schemas ---


class SessionCreateRequest(BaseModel):
    """Optional metadata when creating a session."""

    title: str | None = Field(None, max_length=200)
    context: str | None = Field(None, max_length=500)


class SessionCreateResponse(BaseModel):
    """Response after creating a session."""

    session_id: str
    user_id: str
    title: str | None
    started_at: datetime.datetime
    status: str


class SessionListItem(BaseModel):
    """Summary of a session for listing."""

    session_id: str
    title: str | None
    started_at: datetime.datetime
    ended_at: datetime.datetime | None
    status: str
    turn_count: int
    primary_modality: str | None


class SessionDetailResponse(BaseModel):
    """Full session detail including transcript."""

    session_id: str
    user_id: str
    title: str | None
    started_at: datetime.datetime
    ended_at: datetime.datetime | None
    status: str
    turns: list[dict[str, Any]]
    eos_timeline: list[dict[str, Any]]
    agents_used: list[str]
    primary_modality: str | None


class SessionEndResponse(BaseModel):
    """Response after ending a session."""

    session_id: str
    status: str
    ended_at: datetime.datetime
    duration_seconds: int | None


# --- Helper ---

def _make_session_id() -> str:
    """Generate a unique session ID."""
    import uuid
    return str(uuid.uuid4())


# --- Routes ---


@router.post(
    "",
    response_model=SessionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new therapy session",
)
async def create_session(
    req: SessionCreateRequest | None = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_user),
):
    """
    Create a new therapy session for the authenticated user.

    Returns the session ID which is used to open the WebSocket.
    """
    user_id = str(current_user["_id"])
    now = datetime.datetime.now(datetime.UTC)
    session_id = _make_session_id()

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
        "music_played": [],
        "check_in_scheduled": False,
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


@router.get(
    "",
    response_model=list[SessionListItem],
    summary="List user's sessions",
)
async def list_sessions(
    status: str | None = None,
    limit: int = 50,
    skip: int = 0,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_user),
):
    """
    List all sessions for the authenticated user.

    Query params:
      - status: filter by 'active', 'ended', or 'all' (default)
      - limit: max results (default 50)
      - skip: pagination offset
    """
    user_id = str(current_user["_id"])
    query = {"user_id": user_id}
    if status and status != "all":
        query["status"] = status

    cursor = (
        db.sessions.find(query)
        .sort("started_at", -1)
        .skip(skip)
        .limit(limit)
    )

    sessions = []
    async for doc in cursor:
        sessions.append(
            SessionListItem(
                session_id=doc["session_id"],
                title=doc.get("title"),
                started_at=doc["started_at"],
                ended_at=doc.get("ended_at"),
                status=doc.get("status", "unknown"),
                turn_count=len(doc.get("turns", [])),
                primary_modality=doc.get("primary_modality"),
            )
        )
    return sessions


@router.get(
    "/{session_id}",
    response_model=SessionDetailResponse,
    summary="Get session transcript and details",
)
async def get_session(
    session_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_user),
):
    """
    Get full session details including transcript, EOS timeline, and metadata.

    Enforces user ownership — returns 404 if session belongs to another user.
    """
    user_id = str(current_user["_id"])
    session = await db.sessions.find_one({
        "session_id": session_id,
        "user_id": user_id,
    })

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    return SessionDetailResponse(
        session_id=session["session_id"],
        user_id=session["user_id"],
        title=session.get("title"),
        started_at=session["started_at"],
        ended_at=session.get("ended_at"),
        status=session.get("status", "unknown"),
        turns=session.get("turns", []),
        eos_timeline=session.get("eos_timeline", []),
        agents_used=session.get("agents_used", []),
        primary_modality=session.get("primary_modality"),
    )


@router.delete(
    "/{session_id}",
    response_model=SessionEndResponse,
    summary="End (soft-delete) a session",
)
async def end_session(
    session_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_user),
):
    """
    End a session by setting status='ended' and ended_at timestamp.

    Does not delete data — preserves transcript for longitudinal memory.
    """
    user_id = str(current_user["_id"])
    now = datetime.datetime.now(datetime.UTC)

    # Find existing session
    session = await db.sessions.find_one({
        "session_id": session_id,
        "user_id": user_id,
    })
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    if session.get("status") == "ended":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session already ended",
        )

    # Calculate duration
    started_at = session["started_at"]
    duration = None
    if isinstance(started_at, datetime.datetime):
        duration = int((now - started_at).total_seconds())

    # Update session
    await db.sessions.update_one(
        {"session_id": session_id, "user_id": user_id},
        {
            "$set": {
                "status": "ended",
                "ended_at": now,
                "duration_seconds": duration,
                "updated_at": now,
            }
        },
    )

    logger.info("Session ended: %s for user %s", session_id, user_id)

    return SessionEndResponse(
        session_id=session_id,
        status="ended",
        ended_at=now,
        duration_seconds=duration,
    )
