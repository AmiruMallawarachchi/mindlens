"""Unit tests for Session Memory Save."""

from __future__ import annotations

from datetime import datetime

import pytest
from app.agents.session_memory_save import SessionMemorySave
from app.core.emotional_os import EmotionalOperatingState


class TestSessionMemorySave:
    """Validate session memory save utility agent."""

    @pytest.fixture
    def agent(self) -> SessionMemorySave:
        return SessionMemorySave()

    @pytest.mark.asyncio
    async def test_no_llm(self, agent: SessionMemorySave, agent_context: EmotionalOperatingState) -> None:
        assert agent.llm_tier == "none"
        assert agent.max_tokens == 0

    @pytest.mark.asyncio
    async def test_returns_metadata(self, agent: SessionMemorySave, agent_context: EmotionalOperatingState) -> None:
        result = await agent.run(agent_context)
        assert result.agent_name == "session_memory_save"
        assert result.text == ""
        assert result.metadata["action"] == "save_turn"
        assert "session_id" in result.metadata
        assert "surface_emotion" in result.metadata
        assert "distress_level" in result.metadata
        assert "modality" in result.metadata
        assert "timestamp" in result.metadata

    @pytest.mark.asyncio
    async def test_timestamp_is_iso(self, agent: SessionMemorySave, agent_context: EmotionalOperatingState) -> None:
        result = await agent.run(agent_context)
        ts = result.metadata["timestamp"]
        # Should be a valid ISO timestamp
        parsed = datetime.fromisoformat(ts)
        assert parsed.year == datetime.now().year
