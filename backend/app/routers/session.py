# backend/app/routers/session.py
"""Session router — WebSocket chat pipeline."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.websocket("/ws/{session_id}")
async def websocket_chat() -> None:
    pass
