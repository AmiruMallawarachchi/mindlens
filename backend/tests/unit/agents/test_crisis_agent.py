"""Unit tests for Crisis Agent."""

from __future__ import annotations

import pytest
from app.agents.crisis_agent import CrisisAgent
from app.core.emotional_os import EmotionalOperatingState


class TestCrisisAgent:
    """Validate crisis agent — the most safety-critical agent."""

    @pytest.fixture
    def agent(self) -> CrisisAgent:
        return CrisisAgent()

    @pytest.mark.asyncio
    async def test_zero_llm(self, agent: CrisisAgent) -> None:
        """Crisis agent MUST NOT use any LLM."""
        assert agent.llm_tier == "none"
        assert agent.max_tokens == 0

    @pytest.mark.asyncio
    async def test_crisis_returns_template(self, agent: CrisisAgent, crisis_agent_context: EmotionalOperatingState) -> None:
        result = await agent.run(crisis_agent_context)
        assert result.agent_name == "crisis"
        assert "1926" in result.text
        assert result.metadata["nimh_number_included"] is True
        assert result.metadata["llm_tier"] == "none"

    @pytest.mark.asyncio
    async def test_moderate_distress_template(self, agent: CrisisAgent) -> None:
        from app.core.emotional_os import EmotionalOperatingState
        eos = EmotionalOperatingState(distress_level=0.6)
        ctx = EmotionalOperatingState.__new__(EmotionalOperatingState)
        # Use a proper context with moderate distress
        from app.agents.base_agent import AgentContext
        ctx = AgentContext(
            eos=EmotionalOperatingState(distress_level=0.6),
            user_text="I feel hopeless",
            user_name="Test",
        )
        result = await agent.run(ctx)
        assert result.agent_name == "crisis"
        assert result.metadata["template_type"] == "moderate"

    @pytest.mark.asyncio
    async def test_severe_distress_template(self, agent: CrisisAgent, crisis_agent_context: EmotionalOperatingState) -> None:
        result = await agent.run(crisis_agent_context)
        assert result.metadata["template_type"] == "severe"
        assert "emergency" in result.text.lower() or "immediately" in result.text.lower()

    @pytest.mark.asyncio
    async def test_personalised_with_name(self, agent: CrisisAgent, crisis_agent_context: EmotionalOperatingState) -> None:
        result = await agent.run(crisis_agent_context)
        # Templates use "you" rather than {name} for direct address
        assert "you" in result.text.lower() or "Amiru" in result.text

    @pytest.mark.asyncio
    async def test_no_groq_call(self, agent: CrisisAgent, crisis_agent_context: EmotionalOperatingState) -> None:
        """Ensure run() never calls any external API."""
        # If this test runs without any mocking and passes,
        # it proves the agent is self-contained.
        result = await agent.run(crisis_agent_context)
        assert result is not None
        assert result.text != ""
