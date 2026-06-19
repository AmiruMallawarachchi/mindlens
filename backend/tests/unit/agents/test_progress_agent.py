"""Unit tests for Progress Agent."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.agents.progress_agent import ProgressAgent
from app.core.emotional_os import EmotionalOperatingState


class TestProgressAgent:
    """Validate progress agent behaviour."""

    @pytest.fixture
    def agent(self) -> ProgressAgent:
        return ProgressAgent()

    @pytest.fixture
    def mock_groq(self) -> MagicMock:
        mock = MagicMock()
        mock.chat = AsyncMock(return_value=MagicMock(
            text="You've been showing up consistently, Amiru. That's a real win.",
            model_used="llama-3.1-8b-instant",
            tokens_used=18,
            latency_ms=90.0,
            finish_reason="stop",
        ))
        return mock

    @pytest.mark.asyncio
    async def test_run(self, agent: ProgressAgent, stable_agent_context: EmotionalOperatingState, mock_groq: MagicMock) -> None:
        with patch("app.agents.progress_agent.get_groq_client", return_value=mock_groq):
            result = await agent.run(stable_agent_context)
        assert result.agent_name == "progress"
        assert "Amiru" in result.text

    @pytest.mark.asyncio
    async def test_system_prompt_celebrates_wins(self, agent: ProgressAgent, stable_agent_context: EmotionalOperatingState) -> None:
        prompt = agent._build_system_prompt(stable_agent_context)
        assert "Celebrate" in prompt or "celebrate" in prompt
        assert "never diagnose" in prompt.lower()

    def test_max_tokens(self, agent: ProgressAgent) -> None:
        assert agent.max_tokens == 350
