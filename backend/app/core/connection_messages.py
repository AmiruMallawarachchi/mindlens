"""Message payload helpers for the WebSocket connection manager."""

from __future__ import annotations

from typing import Any


class ConnectionMessageMethods:
    async def send_thinking_update(
        self,
        user_id: str,
        agents_active: list[str],
        eos: dict[str, Any],
        memory_recalled: list[str] | None = None,
        telemetry: dict[str, Any] | None = None,
        safety: dict[str, Any] | None = None,
        degraded: list[str] | None = None,
    ) -> bool:
        """Send a thinking panel update to the client.

        `safety` and `telemetry` exist so the reasoning trail can report what
        happened instead of asserting it. The safety verdict was computed on
        every turn and then dropped here, which left the client rendering the
        sentence "Clear - no crisis signals" as a literal regardless of what
        the gate had actually decided.
        """
        return await self.send_to_user(
            user_id,
            {
                "type": "thinking_update",
                "agents_active": agents_active,
                "eos": eos,
                "memory_recalled": memory_recalled or [],
                "telemetry": telemetry or {},
                "safety": safety or {},
                # The whole pipeline finishes before streaming begins, so
                # degradation is already known here. Without it the live trail
                # had to assume a healthy turn and could not report a fallback
                # while one was happening.
                "degraded": degraded or [],
            },
        )

    async def send_stage_update(
        self,
        user_id: str,
        stage: str,
        detail: str,
    ) -> bool:
        """Announce that one pipeline stage just finished.

        Sent while the pipeline is still running, unlike thinking_update
        which is sent afterwards with the completed picture. This is what
        makes the reasoning trail arrive a step at a time instead of all
        four sections landing at once, already done.
        """
        return await self.send_to_user(
            user_id,
            {"type": "stage_update", "stage": stage, "detail": detail},
        )

    async def send_response(
        self,
        user_id: str,
        text: str,
        agents_used: list[str],
        eos_snapshot: dict[str, Any],
        crisis_flag: bool = False,
        resources: list[dict] | None = None,
        degraded: list[str] | None = None,
        memory_recalled: list[str] | None = None,
        telemetry: dict[str, Any] | None = None,
        safety: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
    ) -> bool:
        """Send the final assembled response to the client."""
        return await self.send_to_user(
            user_id,
            {
                "type": "response",
                "text": text,
                "agents_used": agents_used,
                "eos_snapshot": eos_snapshot,
                "crisis_flag": crisis_flag,
                "resources": resources or [],
                # Reasons this turn fell back to canned text ("stub",
                # "timeout", "api_error"). Empty on a healthy turn.
                "degraded": degraded or [],
                # Previously sent only on thinking_update, which the client
                # attaches to the *user's* bubble (the read of what they just
                # sent). The persisted reasoning trail lives on the assistant
                # turn (message-flow.tsx reads message.memoryRecalled there),
                # so without it here "Memory" silently showed "Nothing from
                # before applies" on every finalized reply even when
                # memory_recall.py had genuinely recalled something.
                "memory_recalled": memory_recalled or [],
                # Same pair as thinking_update: the persisted trail on the
                # assistant turn needs them too, not just the live one.
                "telemetry": telemetry or {},
                "safety": safety or {},
                # Structured follow-up answers, when the reply asked
                # something. None on most turns; never present in crisis.
                "options": options,
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

