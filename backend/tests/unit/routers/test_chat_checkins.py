"""Focused tests for WebSocket chat service behavior."""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.agents.base_agent import AgentOutput
from app.core.connection_manager import ConnectionManager
from app.routers.chat import (
    _CHECKIN_FALLBACK_TEXT,
    _ensure_user_memory_doc,
    _save_extracted_memory,
    _save_introvert_score,
    _save_mood_log,
    _save_pending_checkin,
)
from pymongo.errors import DuplicateKeyError
from .chat_test_fixtures import mock_db_ws, sample_session_doc


class TestSavePendingCheckin:
    """CheckInAgent (SYSTEM.md §5.12) was registered in the orchestrator but
    never dispatched by _select_agents — only checkin_scheduler (which
    decides *when*) ran. Every proactive check-in used a hardcoded generic
    line instead, which is the exact opener the agent's own prompt forbids.
    These pin that the real agent's text is now what gets stored."""

    @pytest.fixture
    def schedule_result(self) -> dict[str, Any]:
        return {
            "eos": {"surface_emotion": "nervousness", "distress_level": 0.6},
            "agent_outputs": [
                {
                    "agent": "checkin_scheduler",
                    "text": "",
                    "metadata": {
                        "action": "schedule_checkin",
                        "scheduled_at": (
                            datetime.datetime.now(datetime.UTC)
                            + datetime.timedelta(hours=12)
                        ).isoformat(),
                    },
                }
            ],
        }

    @pytest.mark.asyncio
    async def test_uses_generated_checkin_text(
        self, mock_db_ws: MagicMock, schedule_result: dict[str, Any]
    ) -> None:
        mock_db_ws.pending_checkins.update_one = AsyncMock()
        generated = AgentOutput(
            agent_name="checkin",
            text="Hey Amiru — how did that exam go in the end?",
            metadata={},
        )
        with patch(
            "app.routers.chat.CheckInAgent.run",
            new=AsyncMock(return_value=generated),
        ):
            await _save_pending_checkin(
                mock_db_ws, "sess_abc", "user_123", "Amiru", [], schedule_result
            )

        mock_db_ws.pending_checkins.update_one.assert_awaited_once()
        _, kwargs = mock_db_ws.pending_checkins.update_one.call_args
        set_fields = mock_db_ws.pending_checkins.update_one.call_args[0][1]["$set"]
        assert set_fields["text"] == "Hey Amiru — how did that exam go in the end?"
        assert set_fields["text"] != "How are you feeling since our last conversation?"

    @pytest.mark.asyncio
    async def test_falls_back_on_generation_failure(
        self, mock_db_ws: MagicMock, schedule_result: dict[str, Any]
    ) -> None:
        mock_db_ws.pending_checkins.update_one = AsyncMock()
        with patch(
            "app.routers.chat.CheckInAgent.run",
            new=AsyncMock(side_effect=RuntimeError("groq down")),
        ):
            await _save_pending_checkin(
                mock_db_ws, "sess_abc", "user_123", "Amiru", [], schedule_result
            )

        mock_db_ws.pending_checkins.update_one.assert_awaited_once()
        set_fields = mock_db_ws.pending_checkins.update_one.call_args[0][1]["$set"]
        assert set_fields["text"] == _CHECKIN_FALLBACK_TEXT

    @pytest.mark.asyncio
    async def test_no_scheduling_action_does_nothing(self, mock_db_ws: MagicMock) -> None:
        mock_db_ws.pending_checkins.update_one = AsyncMock()
        result = {"eos": {}, "agent_outputs": [{"agent": "empathy", "text": "hi", "metadata": {}}]}

        await _save_pending_checkin(mock_db_ws, "sess_abc", "user_123", "Amiru", [], result)

        mock_db_ws.pending_checkins.update_one.assert_not_awaited()
