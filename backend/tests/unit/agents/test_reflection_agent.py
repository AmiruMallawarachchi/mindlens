"""Unit tests for Reflection Agent."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.agents.reflection_agent import ReflectionAgent
from app.core.emotional_os import EmotionalOperatingState


class TestReflectionAgent:
    """Validate reflection agent behaviour."""

    @pytest.fixture
    def agent(self) -> ReflectionAgent:
        return ReflectionAgent()

    @pytest.fixture
    def mock_groq(self) -> MagicMock:
        mock = MagicMock()
        mock.chat = AsyncMock(return_value=MagicMock(
            text="It sounds like you're feeling unseen at work, and that hurts.",
            model_used="llama-3.1-8b-instant",
            tokens_used=12,
            latency_ms=90.0,
            finish_reason="stop",
        ))
        return mock

    @pytest.mark.asyncio
    async def test_run(self, agent: ReflectionAgent, agent_context: EmotionalOperatingState, mock_groq: MagicMock) -> None:
        with patch("app.agents.reflection_agent.get_groq_client", return_value=mock_groq):
            result = await agent.run(agent_context)
        assert result.agent_name == "reflection"
        assert "sounds like" in result.text.lower() or "feeling" in result.text.lower()

    @pytest.mark.asyncio
    async def test_system_prompt_one_sentence(self, agent: ReflectionAgent, agent_context: EmotionalOperatingState) -> None:
        prompt = agent._build_system_prompt(agent_context)
        assert "ONE concise sentence" in prompt
        assert "never diagnose" in prompt.lower()

    def test_max_tokens_small(self, agent: ReflectionAgent) -> None:
        assert agent.max_tokens == 80
