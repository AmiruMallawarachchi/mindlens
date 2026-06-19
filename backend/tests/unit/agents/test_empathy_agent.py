"""Unit tests for Empathy Agent."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.agents.empathy_agent import EmpathyAgent
from app.core.emotional_os import EmotionalOperatingState


class TestEmpathyAgent:
    """Validate empathy agent behaviour."""

    @pytest.fixture
    def agent(self) -> EmpathyAgent:
        return EmpathyAgent()

    @pytest.fixture
    def mock_groq(self) -> MagicMock:
        mock = MagicMock()
        mock.chat = AsyncMock(return_value=MagicMock(
            text="I hear you, Amiru. That sounds really hard.",
            model_used="llama-3.1-8b-instant",
            tokens_used=15,
            latency_ms=120.0,
            finish_reason="stop",
        ))
        return mock

    @pytest.mark.asyncio
    async def test_always_runs(self, agent: EmpathyAgent) -> None:
        assert agent.always_runs is True
        assert agent.name == "empathy"

    @pytest.mark.asyncio
    async def test_run_returns_output(self, agent: EmpathyAgent, agent_context: EmotionalOperatingState, mock_groq: MagicMock) -> None:
        with patch("app.agents.empathy_agent.get_groq_client", return_value=mock_groq):
            result = await agent.run(agent_context)
        assert result.agent_name == "empathy"
        assert "Amiru" in result.text
        # Default distress in fixture is 0.5, which triggers 70B tier
        assert result.metadata["llm_tier"] in ("8B", "70B")

    @pytest.mark.asyncio
    async def test_uses_70b_for_high_distress(self, agent: EmpathyAgent, crisis_agent_context: EmotionalOperatingState, mock_groq: MagicMock) -> None:
        with patch("app.agents.empathy_agent.get_groq_client", return_value=mock_groq):
            result = await agent.run(crisis_agent_context)
        assert result.metadata["llm_tier"] == "70B"

    @pytest.mark.asyncio
    async def test_system_prompt_includes_name(self, agent: EmpathyAgent, agent_context: EmotionalOperatingState) -> None:
        prompt = agent._build_system_prompt(agent_context)
        assert "Empathy Agent" in prompt
        assert "Amiru" in prompt
        assert "never diagnose" in prompt.lower()

    @pytest.mark.asyncio
    async def test_user_prompt_includes_text(self, agent: EmpathyAgent, agent_context: EmotionalOperatingState) -> None:
        prompt = agent._build_user_prompt(agent_context)
        assert "anxious" in prompt

    def test_max_tokens(self, agent: EmpathyAgent) -> None:
        assert agent.max_tokens == 200
