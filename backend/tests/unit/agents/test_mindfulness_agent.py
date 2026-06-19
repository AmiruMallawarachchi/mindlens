"""Unit tests for Mindfulness Agent."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.agents.mindfulness_agent import MindfulnessAgent
from app.core.emotional_os import EmotionalOperatingState


class TestMindfulnessAgent:
    """Validate mindfulness agent behaviour."""

    @pytest.fixture
    def agent(self) -> MindfulnessAgent:
        return MindfulnessAgent()

    @pytest.fixture
    def mock_groq(self) -> MagicMock:
        mock = MagicMock()
        mock.chat = AsyncMock(return_value=MagicMock(
            text="Breathe in for 4… hold for 4… out for 6.",
            model_used="llama-3.1-8b-instant",
            tokens_used=20,
            latency_ms=100.0,
            finish_reason="stop",
        ))
        return mock

    @pytest.mark.asyncio
    async def test_name_and_description(self, agent: MindfulnessAgent) -> None:
        assert agent.name == "mindfulness"
        assert agent.always_runs is False

    @pytest.mark.asyncio
    async def test_run_returns_breathing(self, agent: MindfulnessAgent, agent_context: EmotionalOperatingState, mock_groq: MagicMock) -> None:
        with patch("app.agents.mindfulness_agent.get_groq_client", return_value=mock_groq):
            result = await agent.run(agent_context)
        assert result.agent_name == "mindfulness"
        assert "Breathe" in result.text
        assert result.metadata["llm_tier"] == "8B"

    @pytest.mark.asyncio
    async def test_system_prompt_adapts_to_distress(self, agent: MindfulnessAgent, agent_context: EmotionalOperatingState) -> None:
        # Default distress in fixture is 0.5 → box breathing
        prompt = agent._build_system_prompt(agent_context)
        assert "BOX BREATHING" in prompt or "4-7-8" in prompt or "EMERGENCY" in prompt

    @pytest.mark.asyncio
    async def test_high_distress_emergency(self, agent: MindfulnessAgent, crisis_agent_context: EmotionalOperatingState) -> None:
        prompt = agent._build_system_prompt(crisis_agent_context)
        assert "EMERGENCY GROUNDING" in prompt
        assert "5-4-3-2-1" in prompt

    def test_max_tokens(self, agent: MindfulnessAgent) -> None:
        assert agent.max_tokens == 250
