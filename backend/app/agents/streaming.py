"""
MindLens Streaming Module
=========================
Streams agent output to WebSocket in real time.

This module sits between the Orchestrator and the ConnectionManager,
chunking responses so the frontend sees:
  1. thinking_update  → agents running, EOS snapshot
  2. stream_chunk     → tokens as they arrive
  3. stream_end       → done

Supports both:
  - Real Groq streaming (if groq client supports it)
  - Simulated streaming (chunk full response into word-sized chunks)

All PII is stripped before any model call. All output is validated
before sending to the client.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.agents.base_agent import AgentOutput
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
    ) -> None:
        """Send thinking panel update to client."""
        # mode="json" — see EmotionalOperatingState.to_dict()'s docstring;
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
        music: dict[str, Any] | None = None,
        crisis_flag: bool = False,
        resources: list[dict] | None = None,
        degraded: list[str] | None = None,
        memory_recalled: list[str] | None = None,
        telemetry: dict[str, Any] | None = None,
        safety: dict[str, Any] | None = None,
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
                music=music,
                crisis_flag=crisis_flag,
                resources=resources,
                degraded=degraded,
                memory_recalled=memory_recalled,
                telemetry=telemetry,
                safety=safety,
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
# Orchestrator-to-Streamer bridge
# ---------------------------------------------------------------------------

async def stream_pipeline_result(
    user_id: str,
    session_id: str,
    pipeline_result: dict[str, Any],
    conn_manager=None,
    enable_streaming: bool = True,
) -> None:
    """
    Convenience function: take the full pipeline result and stream it
    to the user's WebSocket.

    Args:
        user_id: MongoDB user _id
        session_id: Current session ID
        pipeline_result: Output from Orchestrator.run_full_pipeline()
        conn_manager: Optional ConnectionManager override
        enable_streaming: If False, sends only the final response (no chunking)
    """
    conn = conn_manager or get_connection_manager()
    streamer = StreamingResponse(user_id, session_id, conn)

    eos = pipeline_result.get("eos", {})
    agents = pipeline_result.get("agents", [])
    crisis_flag = pipeline_result.get("crisis_flag", False)
    assembled_text = pipeline_result.get("assembled_text", "")
    agent_outputs = pipeline_result.get("agent_outputs", [])
    degraded = pipeline_result.get("degraded", [])
    memory_recalled = pipeline_result.get("memory_recalled", [])
    # The safety verdict was computed on every turn and then dropped right
    # here, so the client had nothing to describe and asserted instead.
    telemetry = pipeline_result.get("telemetry", {})
    safety = pipeline_result.get("safety", {})
    music_payload = _extract_music_payload(agent_outputs)

    # Step 1: Thinking update
    await streamer.begin_thinking(
        agents_active=agents,
        eos=eos,
        memory_recalled=memory_recalled,
        telemetry=telemetry,
        safety=safety,
    )

    # Small delay so thinking panel renders before text starts
    await asyncio.sleep(0.2)

    if crisis_flag:
        # Crisis: don't stream, send full response immediately
        resources = []
        for out in agent_outputs:
            if out.get("agent") == "crisis":
                resources = out.get("metadata", {}).get("resources", [])
                break
        await streamer.end_stream(
            assembled_text=assembled_text,
            agents_used=agents,
            eos_snapshot=eos,
            crisis_flag=True,
            resources=resources,
            telemetry=telemetry,
            safety=safety,
        )
    elif enable_streaming and len(assembled_text) > 40:
        # Step 2: Stream text with typing effect
        await streamer.stream_text(assembled_text, chunk_size=DEFAULT_CHUNK_SIZE)
        # Step 3: Send end signal (front-end hides typing, shows final)
        await streamer.end_stream(
            assembled_text=assembled_text,
            agents_used=agents,
            eos_snapshot=eos,
            music=music_payload,
            degraded=degraded,
            memory_recalled=memory_recalled,
            telemetry=telemetry,
            safety=safety,
        )
    else:
        # Short response or streaming disabled: send final directly
        await streamer.end_stream(
            assembled_text=assembled_text,
            agents_used=agents,
            eos_snapshot=eos,
            music=music_payload,
            degraded=degraded,
            memory_recalled=memory_recalled,
            telemetry=telemetry,
            safety=safety,
        )


def _extract_music_payload(agent_outputs: list[dict[str, Any]]) -> dict[str, Any] | None:
    """
    Shape the music agent's output into the structured `music` field the
    WebSocket response carries. `end_stream`/`send_response` have accepted a
    `music` payload since they were written; nothing ever built one to pass —
    the field was always sent as null regardless of whether music_agent ran.

    Returns None when the music agent didn't run this turn, so the frontend
    can tell "no music this turn" apart from "music with nothing in it".
    """
    music_output = next(
        (o for o in agent_outputs if o.get("agent") == "music"), None
    )
    if music_output is None:
        return None

    metadata = music_output.get("metadata", {})
    return {
        "message": music_output.get("text", ""),
        "tracks": metadata.get("tracks", []),
        "emotion": metadata.get("emotion"),
    }


async def stream_agent_output(
    user_id: str,
    session_id: str,
    agent_output: AgentOutput,
    eos: EmotionalOperatingState | dict[str, Any],
    conn_manager=None,
) -> None:
    """
    Stream a single agent's output directly (for specialized agents
    that run outside the full orchestrator pipeline, e.g. music agent).
    """
    conn = conn_manager or get_connection_manager()
    streamer = StreamingResponse(user_id, session_id, conn)

    await streamer.begin_thinking(
        agents_active=[agent_output.agent_name],
        eos=eos,
    )

    await asyncio.sleep(0.15)

    await streamer.stream_text(agent_output.text, chunk_size=DEFAULT_CHUNK_SIZE)
    await streamer.end_stream(
        assembled_text=agent_output.text,
        agents_used=[agent_output.agent_name],
        eos_snapshot=eos,
    )
