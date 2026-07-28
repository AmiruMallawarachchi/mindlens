"""Unit tests for Reflection Agent — MindLens v3 SYSTEM.md §5.5."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.agents.base_agent import AgentContext
from app.agents.reflection_agent import ReflectionAgent
from app.core.emotional_os import EmotionalOperatingState


class TestReflectionAgent:
    """Validate reflection agent v3 behaviour."""

    @pytest.fixture
    def agent(self) -> ReflectionAgent:
        return ReflectionAgent()

    @pytest.fixture
    def mock_groq(self) -> MagicMock:
        mock = MagicMock()
        mock.chat = AsyncMock(return_value=MagicMock(
            text="It sounds like you're feeling really anxious about this, Amiru.",
            model_used="llama-3.1-8b-instant",
            tokens_used=15,
            latency_ms=120.0,
            finish_reason="stop",
        ))
        return mock

    @pytest.mark.asyncio
    async def test_skips_when_session_depth_low(self, agent: ReflectionAgent) -> None:
        """SYSTEM.md §5.5: Only runs when session_depth > 0.3."""
        eos = EmotionalOperatingState(session_depth=0.1)
        ctx = AgentContext(eos=eos, user_text="test", user_name="Amiru")
        result = await agent.run(ctx)
        assert result.metadata["skipped"] is True
        assert result.metadata["reason"] == "session_depth <= 0.3"
        assert result.metadata["llm_tier"] == "none"
        assert result.text == ""

    @pytest.mark.asyncio
    async def test_runs_when_session_depth_high(self, agent: ReflectionAgent, mock_groq: MagicMock) -> None:
        """SYSTEM.md §5.5: Runs when session_depth > 0.3."""
        eos = EmotionalOperatingState(session_depth=0.4)
        ctx = AgentContext(eos=eos, user_text="test", user_name="Amiru")
        with patch("app.agents.reflection_agent.get_groq_client", return_value=mock_groq):
            result = await agent.run(ctx)
        assert result.metadata["skipped"] is not True
        assert result.metadata["llm_tier"] == "8B"
        assert result.text != ""

    @pytest.mark.asyncio
    async def test_uses_8b_model(self, agent: ReflectionAgent, mock_groq: MagicMock) -> None:
        """SYSTEM.md §5.5: Uses 8B model (fast, lightweight)."""
        eos = EmotionalOperatingState(session_depth=0.5)
        ctx = AgentContext(eos=eos, user_text="test", user_name="Amiru")
        with patch("app.agents.reflection_agent.get_groq_client", return_value=mock_groq):
            result = await agent.run(ctx)
        assert result.metadata["llm_tier"] == "8B"

    @pytest.mark.asyncio
    async def test_max_tokens_50(self, agent: ReflectionAgent) -> None:
        """SYSTEM.md §5.5: Max 50 tokens = 1 sentence."""
        assert agent.max_tokens == 50

    def test_system_prompt_v3_includes_name(self, agent: ReflectionAgent) -> None:
        """SYSTEM.md §5.5: Use name once."""
        eos = EmotionalOperatingState(surface_emotion="anxiety")
        ctx = AgentContext(eos=eos, user_text="test", user_name="Amiru")
        prompt = agent._build_system_prompt_v3(ctx)
        assert "Amiru" in prompt

    def test_system_prompt_v3_one_sentence_only(self, agent: ReflectionAgent) -> None:
        """SYSTEM.md §5.5: ONE sentence."""
        eos = EmotionalOperatingState()
        ctx = AgentContext(eos=eos, user_text="test", user_name="Amiru")
        prompt = agent._build_system_prompt_v3(ctx)
        assert "ONE sentence" in prompt

    def test_system_prompt_v3_no_advice(self, agent: ReflectionAgent) -> None:
        """SYSTEM.md §5.5: No advice."""
        eos = EmotionalOperatingState()
        ctx = AgentContext(eos=eos, user_text="test", user_name="Amiru")
        prompt = agent._build_system_prompt_v3(ctx)
        assert "Do NOT give advice" in prompt

    def test_system_prompt_v3_no_questions(self, agent: ReflectionAgent) -> None:
        """SYSTEM.md §5.5: No questions."""
        eos = EmotionalOperatingState()
        ctx = AgentContext(eos=eos, user_text="test", user_name="Amiru")
        prompt = agent._build_system_prompt_v3(ctx)
        assert "Do NOT ask questions" in prompt

    def test_system_prompt_v3_no_forbidden_phrases(self, agent: ReflectionAgent) -> None:
        """SYSTEM.md §5.5: Never use forbidden phrases."""
        eos = EmotionalOperatingState()
        ctx = AgentContext(eos=eos, user_text="test", user_name="Amiru")
        prompt = agent._build_system_prompt_v3(ctx)
        assert "NEVER use" in prompt
        assert "I understand your feelings" in prompt

    def test_system_prompt_v3_validate_emotion(self, agent: ReflectionAgent) -> None:
        """SYSTEM.md §5.5: Validate user's emotion."""
        eos = EmotionalOperatingState(surface_emotion="sadness")
        ctx = AgentContext(eos=eos, user_text="test", user_name="Amiru")
        prompt = agent._build_system_prompt_v3(ctx)
        assert "sadness" in prompt
        assert "validates" in prompt.lower() or "validate" in prompt.lower()

    def test_system_prompt_v3_genuine_not_clinical(self, agent: ReflectionAgent) -> None:
        """SYSTEM.md §5.5: Make it feel genuine, not clinical."""
        eos = EmotionalOperatingState()
        ctx = AgentContext(eos=eos, user_text="test", user_name="Amiru")
        prompt = agent._build_system_prompt_v3(ctx)
        assert "genuine, not clinical" in prompt

    def test_not_always_runs(self, agent: ReflectionAgent) -> None:
        assert agent.always_runs is False
        assert agent.name == "reflection"
