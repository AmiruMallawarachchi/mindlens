"""Unit tests for CheckIn Agent."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.agents.checkin_agent import CheckInAgent
from app.core.emotional_os import EmotionalOperatingState


class TestCheckInAgent:
    """Validate check-in agent behaviour."""

    @pytest.fixture
    def agent(self) -> CheckInAgent:
        return CheckInAgent()

    @pytest.fixture
    def mock_groq(self) -> MagicMock:
        mock = MagicMock()
        mock.chat = AsyncMock(return_value=MagicMock(
            text="Hey Amiru, just checking in. How are you feeling today?",
            model_used="llama-3.1-8b-instant",
            tokens_used=12,
            latency_ms=80.0,
            finish_reason="stop",
        ))
        return mock

    @pytest.mark.asyncio
    async def test_run(self, agent: CheckInAgent, agent_context: EmotionalOperatingState, mock_groq: MagicMock) -> None:
        with patch("app.agents.checkin_agent.get_groq_client", return_value=mock_groq):
            result = await agent.run(agent_context)
        assert result.agent_name == "checkin"
        assert "Amiru" in result.text

    @pytest.mark.asyncio
    async def test_system_prompt_brief(self, agent: CheckInAgent, agent_context: EmotionalOperatingState) -> None:
        prompt = agent._build_system_prompt(agent_context)
        assert "2-3 sentences" in prompt
        assert "gentle" in prompt.lower()

    def test_max_tokens(self, agent: CheckInAgent) -> None:
        assert agent.max_tokens == 100
