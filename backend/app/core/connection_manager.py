"""
MindLens WebSocket Connection Manager
====================================
Manages WebSocket connection lifecycle, heartbeats, and per-user
connection enforcement. Singleton pattern — one manager per app.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

from fastapi import WebSocket

from app.utils.logger import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    """
    Central WebSocket connection manager.

    Features:
    - Track active connections by user_id
    - Enforce max one connection per user
    - Heartbeat/ping to detect dead connections
    - Broadcast to specific user or all connections
    - Graceful cleanup on disconnect
    """

    def __init__(
        self,
        heartbeat_interval: int = 30,
        max_concurrent_per_user: int = 1,
    ) -> None:
        self._connections: dict[str, WebSocket] = {}
        self._metadata: dict[str, dict[str, Any]] = {}
        self._heartbeat_interval = heartbeat_interval
        self._max_concurrent = max_concurrent_per_user
        self._heartbeat_tasks: dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    # -----------------------------------------------------------------------
    # Connection lifecycle
    # -----------------------------------------------------------------------

    async def connect(
        self,
        websocket: WebSocket,
        user_id: str,
        session_id: str | None = None,
    ) -> bool:
        """
        Accept a new WebSocket connection.

        Returns True if connected, False if rejected (max concurrent).
        If a previous connection exists for this user, it is closed.
        """
        async with self._lock:
            # Enforce single connection per user
            if user_id in self._connections:
                old_ws = self._connections[user_id]
                try:
                    await old_ws.close(code=4009, reason="New connection opened")
                    logger.info("Closed previous connection for user %s", user_id)
                except Exception:
                    pass
                # Cancel old heartbeat
                old_task = self._heartbeat_tasks.pop(user_id, None)
                if old_task:
                    old_task.cancel()

            await websocket.accept()
            self._connections[user_id] = websocket
            self._metadata[user_id] = {
                "connected_at": time.time(),
                "session_id": session_id or str(uuid.uuid4()),
                "last_activity": time.time(),
                "message_count": 0,
            }

            # Start heartbeat
            self._heartbeat_tasks[user_id] = asyncio.create_task(
                self._heartbeat_loop(user_id, websocket)
            )

            logger.info(
                "WebSocket connected: user=%s session=%s total=%d",
                user_id,
                self._metadata[user_id]["session_id"],
                len(self._connections),
            )
            return True

    async def disconnect(self, user_id: str) -> None:
        """Remove a connection and clean up resources."""
        async with self._lock:
            ws = self._connections.pop(user_id, None)
            meta = self._metadata.pop(user_id, None)
            task = self._heartbeat_tasks.pop(user_id, None)
            if task:
                task.cancel()

        if ws:
            try:
                await ws.close()
            except Exception:
                pass

        if meta:
            logger.info(
                "WebSocket disconnected: user=%s session=%s duration=%.1fs",
                user_id,
                meta.get("session_id", "unknown"),
                time.time() - meta.get("connected_at", time.time()),
            )

    # -----------------------------------------------------------------------
    # Messaging
    # -----------------------------------------------------------------------

    async def send_to_user(self, user_id: str, message: dict[str, Any]) -> bool:
        """Send a JSON message to a specific user's WebSocket."""
        ws = self._connections.get(user_id)
        if ws is None:
            return False
        try:
            await ws.send_json(message)
            # Update activity
            meta = self._metadata.get(user_id)
            if meta:
                meta["last_activity"] = time.time()
                meta["message_count"] = meta.get("message_count", 0) + 1
            return True
        except Exception as exc:
            logger.warning("Failed to send to user %s: %s", user_id, exc)
            asyncio.create_task(self.disconnect(user_id))
            return False

    async def send_thinking_update(
        self,
        user_id: str,
        agents_active: list[str],
        eos: dict[str, Any],
        memory_recalled: list[str] | None = None,
    ) -> bool:
        """Send a thinking panel update to the client."""
        return await self.send_to_user(
            user_id,
            {
                "type": "thinking_update",
                "agents_active": agents_active,
                "eos": eos,
                "memory_recalled": memory_recalled or [],
            },
        )

    async def send_response(
        self,
        user_id: str,
        text: str,
        agents_used: list[str],
        eos_snapshot: dict[str, Any],
        music: dict[str, Any] | None = None,
        crisis_flag: bool = False,
        resources: list[dict] | None = None,
    ) -> bool:
        """Send the final assembled response to the client."""
        return await self.send_to_user(
            user_id,
            {
                "type": "response",
                "text": text,
                "agents_used": agents_used,
                "eos_snapshot": eos_snapshot,
                "music": music,
                "crisis_flag": crisis_flag,
                "resources": resources or [],
            },
        )

    async def send_crisis_response(
        self,
        user_id: str,
        text: str,
        resources: list[dict],
    ) -> bool:
        """Send a crisis response to the client."""
        return await self.send_to_user(
            user_id,
            {
                "type": "crisis_response",
                "text": text,
                "crisis_flag": True,
                "resources": resources,
                "session_paused": True,
            },
        )

    async def send_chunk(self, user_id: str, chunk: str, chunk_index: int) -> bool:
        """Send a streaming text chunk to the client."""
        return await self.send_to_user(
            user_id,
            {
                "type": "stream_chunk",
                "chunk": chunk,
                "index": chunk_index,
            },
        )

    async def send_stream_end(self, user_id: str) -> bool:
        """Signal the end of a streaming response."""
        return await self.send_to_user(
            user_id,
            {"type": "stream_end"},
        )

    async def send_checkin(self, user_id: str, text: str, from_session: str) -> bool:
        """Send a proactive check-in message on session open."""
        return await self.send_to_user(
            user_id,
            {
                "type": "checkin",
                "text": text,
                "from_session": from_session,
            },
        )

    # -----------------------------------------------------------------------
    # Heartbeat
    # -----------------------------------------------------------------------

    async def _heartbeat_loop(self, user_id: str, websocket: WebSocket) -> None:
        """Periodic ping to keep connection alive and detect dead clients."""
        try:
            while True:
                await asyncio.sleep(self._heartbeat_interval)
                if user_id not in self._connections:
                    break
                try:
                    await websocket.send_json({"type": "ping", "timestamp": time.time()})
                except Exception:
                    logger.warning("Heartbeat failed for user %s, closing", user_id)
                    await self.disconnect(user_id)
                    break
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.warning("Heartbeat loop error for user %s: %s", user_id, exc)

    # -----------------------------------------------------------------------
    # Queries
    # -----------------------------------------------------------------------

    def is_connected(self, user_id: str) -> bool:
        return user_id in self._connections

    def get_connection_count(self) -> int:
        return len(self._connections)

    def get_user_session_id(self, user_id: str) -> str | None:
        meta = self._metadata.get(user_id)
        return meta.get("session_id") if meta else None

    def get_all_connected_users(self) -> list[str]:
        return list(self._connections.keys())

    def get_metadata(self, user_id: str) -> dict[str, Any] | None:
        return self._metadata.get(user_id)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_manager: ConnectionManager | None = None


def get_connection_manager(
    heartbeat_interval: int | None = None,
    max_concurrent_per_user: int | None = None,
) -> ConnectionManager:
    """Return the global ConnectionManager singleton."""
    global _manager
    if _manager is None:
        from app.config import settings
        _manager = ConnectionManager(
            heartbeat_interval=heartbeat_interval or settings.WS_HEARTBEAT_INTERVAL_SECONDS,
            max_concurrent_per_user=max_concurrent_per_user or settings.WS_MAX_CONCURRENT_PER_USER,
        )
    return _manager
