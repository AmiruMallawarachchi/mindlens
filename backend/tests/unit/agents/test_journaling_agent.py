"""Unit tests for Journaling Agent."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.agents.journaling_agent import JournalingAgent
from app.core.emotional_os import EmotionalOperatingState


class TestJournalingAgent:
    """Validate journaling agent behaviour."""

    @pytest.fixture
    def agent(self) -> JournalingAgent:
        return JournalingAgent()

    @pytest.fixture
    def mock_groq(self) -> MagicMock:
        mock = MagicMock()
        mock.chat = AsyncMock(return_value=MagicMock(
            text="1. What emotion showed up today?\n2. What felt hardest?\n3. What went okay?",
            model_used="llama-3.1-8b-instant",
            tokens_used=18,
            latency_ms=85.0,
            finish_reason="stop",
        ))
        return mock

    @pytest.mark.asyncio
    async def test_run(self, agent: JournalingAgent, agent_context: EmotionalOperatingState, mock_groq: MagicMock) -> None:
        with patch("app.agents.journaling_agent.get_groq_client", return_value=mock_groq):
            result = await agent.run(agent_context)
        assert result.agent_name == "journaling"
        assert "1." in result.text
        assert "?" in result.text

    @pytest.mark.asyncio
    async def test_system_prompt_three_questions(self, agent: JournalingAgent, agent_context: EmotionalOperatingState) -> None:
        prompt = agent._build_system_prompt(agent_context)
        assert "exactly 3" in prompt.lower()
        assert "never diagnose" in prompt.lower()

    def test_max_tokens(self, agent: JournalingAgent) -> None:
        assert agent.max_tokens == 150
