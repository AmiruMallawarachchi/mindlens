"""Focused tests for WebSocket chat service behavior."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from app.routers.chat_services.persistence import _save_mood_log


class TestSaveMoodLog:
    """dashboard.py's /mood and /summary read this collection — nothing
    wrote to it until _save_mood_log existed. These tests pin that a normal
    turn logs the real EOS reading, and a crisis turn logs nothing."""

    @pytest.mark.asyncio
    async def test_normal_turn_logs_eos_snapshot(self, mock_db_ws: MagicMock) -> None:
        result = {
            "crisis_flag": False,
            "eos": {
                "surface_emotion": "nervousness",
                "core_emotion": "fear",
                "distress_level": 0.62,
                "valence": "negative",
                "modality": "CBT",
            },
        }

        await _save_mood_log(mock_db_ws, "sess_abc", "user_123", result)

        mock_db_ws.mood_logs.insert_one.assert_awaited_once()
        logged = mock_db_ws.mood_logs.insert_one.call_args[0][0]
        assert logged["user_id"] == "user_123"
        assert logged["session_id"] == "sess_abc"
        assert logged["surface_emotion"] == "nervousness"
        assert logged["distress_level"] == 0.62
        assert "timestamp" in logged

    @pytest.mark.asyncio
    async def test_crisis_turn_is_not_logged(self, mock_db_ws: MagicMock) -> None:
        """Crisis EOS is a hardcoded placeholder (orchestrator.py sets
        distress_level=1.0 unconditionally), not a real inference — logging
        it would fabricate a mood-trend data point."""
        result = {
            "crisis_flag": True,
            "eos": {
                "surface_emotion": "distress",
                "distress_level": 1.0,
            },
        }

        await _save_mood_log(mock_db_ws, "sess_abc", "user_123", result)

        mock_db_ws.mood_logs.insert_one.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_missing_eos_fields_do_not_raise(self, mock_db_ws: MagicMock) -> None:
        result = {"crisis_flag": False, "eos": {}}

        await _save_mood_log(mock_db_ws, "sess_abc", "user_123", result)

        mock_db_ws.mood_logs.insert_one.assert_awaited_once()
        logged = mock_db_ws.mood_logs.insert_one.call_args[0][0]
        assert logged["surface_emotion"] is None
