"""WebSocket response chunking and lifecycle messages."""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.connection_manager import get_connection_manager
from app.core.emotional_os import EmotionalOperatingState
from app.utils.logger import get_logger

logger = get_logger(__name__)
# Simulated streaming chunk size (characters per chunk)
DEFAULT_CHUNK_SIZE = 8
STREAM_DELAY_MS = 30  # artificial delay between chunks for natural feel


class StreamingResponse:
    """
    Handles streaming a single agent's response to a user's WebSocket.

    Usage:
        streamer = StreamingResponse(user_id, session_id, connection_manager)
        await streamer.begin_thinking(["empathy_agent", "mindfulness_agent"], eos)
        await streamer.stream_text(full_text, chunk_size=8)
        await streamer.end_stream(agents_used, eos_snapshot)
    """

    def __init__(
        self,
        user_id: str,
        session_id: str,
        conn_manager=None,
    ) -> None:
        self.user_id = user_id
        self.session_id = session_id
        self.conn_manager = conn_manager or get_connection_manager()
        self._chunk_index = 0

    # -----------------------------------------------------------------------
    # Phase 1: Thinking update
    # -----------------------------------------------------------------------

    async def begin_thinking(
        self,
        agents_active: list[str],
        eos: EmotionalOperatingState | dict[str, Any],
        memory_recalled: list[str] | None = None,
        telemetry: dict[str, Any] | None = None,
        safety: dict[str, Any] | None = None,
        degraded: list[str] | None = None,
    ) -> None:
        """Send thinking panel update to client."""
        # mode="json" â€” see EmotionalOperatingState.to_dict()'s docstring;
        # a plain model_dump() here leaves any populated datetime field
        # (PeopleGraph.mentioned_at, etc.) unserializable by send_json().
        eos_dict = (
            eos.model_dump(mode="json") if isinstance(eos, EmotionalOperatingState) else eos
        )
        await self.conn_manager.send_thinking_update(
            user_id=self.user_id,
            agents_active=agents_active,
            eos=eos_dict,
            memory_recalled=memory_recalled,
            telemetry=telemetry,
            safety=safety,
            degraded=degraded,
        )

    # -----------------------------------------------------------------------
    # Phase 2: Stream text chunks
    # -----------------------------------------------------------------------

    async def stream_text(
        self,
        text: str,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        delay_ms: float = STREAM_DELAY_MS,
    ) -> None:
        """
        Break text into chunks and send sequentially over WebSocket.

        Creates a typing effect for the frontend.
        """
        if not text:
            return

        # Simple chunking: by character count, respecting word boundaries where possible
        chunks = self._chunk_text(text, chunk_size)
        for chunk in chunks:
            await self.conn_manager.send_chunk(
                user_id=self.user_id,
                chunk=chunk,
                chunk_index=self._chunk_index,
            )
            self._chunk_index += 1
            if delay_ms > 0 and len(chunks) > 1:
                await asyncio.sleep(delay_ms / 1000.0)

    # -----------------------------------------------------------------------
    # Phase 3: Final assembled response
    # -----------------------------------------------------------------------

    async def end_stream(
        self,
        assembled_text: str,
        agents_used: list[str],
        eos_snapshot: EmotionalOperatingState | dict[str, Any],
        crisis_flag: bool = False,
        resources: list[dict] | None = None,
        degraded: list[str] | None = None,
        memory_recalled: list[str] | None = None,
        telemetry: dict[str, Any] | None = None,
        safety: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
    ) -> None:
        """
        Send final response payload.

        If streaming was used, this sends the complete verified text
        along with metadata. If streaming was NOT used, this is the
        primary message that carries the full response.
        """
        eos_dict = (
            eos_snapshot.model_dump(mode="json")
            if isinstance(eos_snapshot, EmotionalOperatingState)
            else eos_snapshot
        )

        if crisis_flag:
            await self.conn_manager.send_crisis_response(
                user_id=self.user_id,
                text=assembled_text,
                resources=resources or [],
            )
        else:
            await self.conn_manager.send_response(
                user_id=self.user_id,
                text=assembled_text,
                agents_used=agents_used,
                eos_snapshot=eos_dict,
                crisis_flag=crisis_flag,
                resources=resources,
                degraded=degraded,
                memory_recalled=memory_recalled,
                telemetry=telemetry,
                safety=safety,
                options=options,
            )

    # -----------------------------------------------------------------------
    # Utilities
    # -----------------------------------------------------------------------

    @staticmethod
    def _chunk_text(text: str, chunk_size: int) -> list[str]:
        """
        Split text into chunks of roughly `chunk_size` characters.
        Tries to respect word boundaries (spaces) for natural feel.
        """
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            if end >= len(text):
                chunks.append(text[start:])
                break
            # Try to break at space
            while end > start and text[end] not in " \n":
                end -= 1
            if end == start:
                # No space found, just hard break
                end = start + chunk_size
            chunks.append(text[start:end])
            start = end
        return chunks


# ---------------------------------------------------------------------------

