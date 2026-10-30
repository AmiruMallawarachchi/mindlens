"""Bridge completed pipeline results to the WebSocket response stream."""

from __future__ import annotations

import asyncio
from typing import Any

from app.agents.streaming_response import DEFAULT_CHUNK_SIZE, StreamingResponse
from app.core.connection_manager import get_connection_manager


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
    options_payload = pipeline_result.get("options")

    # Step 1: Thinking update
    await streamer.begin_thinking(
        agents_active=agents,
        eos=eos,
        memory_recalled=memory_recalled,
        telemetry=telemetry,
        safety=safety,
        degraded=degraded,
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
            degraded=degraded,
            memory_recalled=memory_recalled,
            telemetry=telemetry,
            safety=safety,
            options=options_payload,
        )
    else:
        # Short response or streaming disabled: send final directly
        await streamer.end_stream(
            assembled_text=assembled_text,
            agents_used=agents,
            eos_snapshot=eos,
            degraded=degraded,
            memory_recalled=memory_recalled,
            telemetry=telemetry,
            safety=safety,
            options=options_payload,
        )

