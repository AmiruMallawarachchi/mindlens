"""Unit tests for Challenge Agent."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.agents.challenge_agent import ChallengeAgent
from app.core.emotional_os import EmotionalOperatingState


class TestChallengeAgent:
    """Validate challenge agent behaviour."""

    @pytest.fixture
    def agent(self) -> ChallengeAgent:
        return ChallengeAgent()

    @pytest.fixture
    def mock_groq(self) -> MagicMock:
        mock = MagicMock()
        mock.chat = AsyncMock(return_value=MagicMock(
            text="What evidence do you have that thought is true?",
            model_used="llama-3.1-8b-instant",
            tokens_used=10,
            latency_ms=80.0,
            finish_reason="stop",
        ))
        return mock

    @pytest.mark.asyncio
    async def test_run(self, agent: ChallengeAgent, stable_agent_context: EmotionalOperatingState, mock_groq: MagicMock) -> None:
        with patch("app.agents.challenge_agent.get_groq_client", return_value=mock_groq):
            result = await agent.run(stable_agent_context)
        assert result.agent_name == "challenge"
        assert "?" in result.text

    @pytest.mark.asyncio
    async def test_system_prompt_gentle(self, agent: ChallengeAgent, stable_agent_context: EmotionalOperatingState) -> None:
        prompt = agent._build_system_prompt(stable_agent_context)
        assert "gentle" in prompt.lower()
        assert "ONE gentle" in prompt
        assert "never diagnose" in prompt.lower()

    def test_max_tokens(self, agent: ChallengeAgent) -> None:
        assert agent.max_tokens == 100
