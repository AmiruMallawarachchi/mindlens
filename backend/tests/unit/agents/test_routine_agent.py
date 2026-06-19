"""Unit tests for Routine Agent."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.agents.routine_agent import RoutineAgent
from app.core.emotional_os import EmotionalOperatingState


class TestRoutineAgent:
    """Validate routine agent behaviour."""

    @pytest.fixture
    def agent(self) -> RoutineAgent:
        return RoutineAgent()

    @pytest.fixture
    def mock_groq(self) -> MagicMock:
        mock = MagicMock()
        mock.chat = AsyncMock(return_value=MagicMock(
            text="1. Drink a glass of water. 2. Step outside for 2 minutes.",
            model_used="llama-3.1-8b-instant",
            tokens_used=20,
            latency_ms=100.0,
            finish_reason="stop",
        ))
        return mock

    @pytest.mark.asyncio
    async def test_run(self, agent: RoutineAgent, agent_context: EmotionalOperatingState, mock_groq: MagicMock) -> None:
        with patch("app.agents.routine_agent.get_groq_client", return_value=mock_groq):
            result = await agent.run(agent_context)
        assert result.agent_name == "routine"
        assert "1." in result.text

    @pytest.mark.asyncio
    async def test_system_prompt_tiny_routine(self, agent: RoutineAgent, agent_context: EmotionalOperatingState) -> None:
        prompt = agent._build_system_prompt(agent_context)
        assert "tiny routine" in prompt.lower()
        assert "2-3 steps max" in prompt

    def test_max_tokens(self, agent: RoutineAgent) -> None:
        assert agent.max_tokens == 350
