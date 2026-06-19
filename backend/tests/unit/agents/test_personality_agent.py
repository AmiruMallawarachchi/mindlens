"""Unit tests for Personality Agent."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.agents.personality_agent import PersonalityAgent
from app.core.emotional_os import EmotionalOperatingState


class TestPersonalityAgent:
    """Validate personality agent behaviour."""

    @pytest.fixture
    def agent(self) -> PersonalityAgent:
        return PersonalityAgent()

    @pytest.fixture
    def mock_groq(self) -> MagicMock:
        mock = MagicMock()
        mock.chat = AsyncMock(return_value=MagicMock(
            text="Use a quiet, non-intrusive tone; respect their space.",
            model_used="llama-3.1-8b-instant",
            tokens_used=10,
            latency_ms=70.0,
            finish_reason="stop",
        ))
        return mock

    @pytest.mark.asyncio
    async def test_run(self, agent: PersonalityAgent, agent_context: EmotionalOperatingState, mock_groq: MagicMock) -> None:
        with patch("app.agents.personality_agent.get_groq_client", return_value=mock_groq):
            result = await agent.run(agent_context)
        assert result.agent_name == "personality"
        assert result.metadata["tone_directive"] is True

    @pytest.mark.asyncio
    async def test_system_prompt_one_sentence(self, agent: PersonalityAgent, agent_context: EmotionalOperatingState) -> None:
        prompt = agent._build_system_prompt(agent_context)
        assert "ONE-SENTENCE" in prompt
        assert "tone" in prompt.lower()

    def test_max_tokens(self, agent: PersonalityAgent) -> None:
        assert agent.max_tokens == 100
