"""Unit tests for Challenge Agent — MindLens v3 SYSTEM.md §5.6."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.agents.base_agent import AgentContext
from app.agents.challenge_agent import ChallengeAgent
from app.core.emotional_os import EmotionalOperatingState, Receptiveness


class TestChallengeAgent:
    """Validate challenge agent v3 gating and behaviour."""

    @pytest.fixture
    def agent(self) -> ChallengeAgent:
        return ChallengeAgent()

    @pytest.fixture
    def mock_groq(self) -> MagicMock:
        mock = MagicMock()
        mock.chat = AsyncMock(return_value=MagicMock(
            text="What would you tell Ravi if he felt the same way you do right now, Amiru?",
            model_used="llama-3.3-70b-versatile",
            tokens_used=25,
            latency_ms=800.0,
            finish_reason="stop",
        ))
        return mock

    # -----------------------------------------------------------------------
    # Gating tests
    # -----------------------------------------------------------------------

    def test_never_runs_on_first_session(self, agent: ChallengeAgent) -> None:
        """SYSTEM.md §5.6: NEVER runs on first session (session_depth < 0.1)."""
        eos = EmotionalOperatingState(session_depth=0.05, trust_level=0.8, emotional_stability=0.8, distress_level=0.3)
        ctx = AgentContext(eos=eos, user_text="test", user_name="Amiru")
        reason = agent._should_run(ctx)
        assert reason is not None
        assert "first_session" in reason

    def test_never_runs_when_distress_high(self, agent: ChallengeAgent) -> None:
        """SYSTEM.md §5.6: NEVER runs when distress > 0.7."""
        eos = EmotionalOperatingState(session_depth=0.5, trust_level=0.8, emotional_stability=0.8, distress_level=0.8)
        ctx = AgentContext(eos=eos, user_text="test", user_name="Amiru")
        reason = agent._should_run(ctx)
        assert reason is not None
        assert "distress_too_high" in reason

    def test_skips_when_trust_low(self, agent: ChallengeAgent) -> None:
        """SYSTEM.md §5.6: trust_level > 0.6 required."""
        eos = EmotionalOperatingState(session_depth=0.5, trust_level=0.5, emotional_stability=0.8, distress_level=0.3)
        ctx = AgentContext(eos=eos, user_text="test", user_name="Amiru")
        reason = agent._should_run(ctx)
        assert reason is not None
        assert "trust_too_low" in reason

    def test_skips_when_stability_low(self, agent: ChallengeAgent) -> None:
        """SYSTEM.md §5.6: emotional_stability > 0.5 required."""
        eos = EmotionalOperatingState(session_depth=0.5, trust_level=0.8, emotional_stability=0.4, distress_level=0.3)
        ctx = AgentContext(eos=eos, user_text="test", user_name="Amiru")
        reason = agent._should_run(ctx)
        assert reason is not None
        assert "stability_too_low" in reason

    def test_skips_when_challenge_not_receptive(self, agent: ChallengeAgent) -> None:
        """SYSTEM.md §5.6: receptiveness.challenge > 0.3 required."""
        eos = EmotionalOperatingState(
            session_depth=0.5, trust_level=0.8, emotional_stability=0.8, distress_level=0.3,
            receptiveness=Receptiveness(challenge=0.2)
        )
        ctx = AgentContext(eos=eos, user_text="test", user_name="Amiru")
        reason = agent._should_run(ctx)
        assert reason is not None
        assert "challenge_not_receptive" in reason

    def test_runs_when_all_gates_pass(self, agent: ChallengeAgent) -> None:
        """All gates pass → should_run returns None."""
        eos = EmotionalOperatingState(
            session_depth=0.5, trust_level=0.8, emotional_stability=0.8, distress_level=0.3,
            receptiveness=Receptiveness(challenge=0.5)
        )
        ctx = AgentContext(eos=eos, user_text="test", user_name="Amiru")
        reason = agent._should_run(ctx)
        assert reason is None

    @pytest.mark.asyncio
    async def test_skipped_run_returns_empty(self, agent: ChallengeAgent) -> None:
        """When gated out, returns empty text with skip metadata."""
        eos = EmotionalOperatingState(session_depth=0.05)
        ctx = AgentContext(eos=eos, user_text="test", user_name="Amiru")
        result = await agent.run(ctx)
        assert result.metadata["skipped"] is True
        assert result.text == ""
        assert result.metadata["llm_tier"] == "none"

    # -----------------------------------------------------------------------
    # Model and prompt tests
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_uses_70b_model(self, agent: ChallengeAgent, mock_groq: MagicMock) -> None:
        """SYSTEM.md §5.6: Uses 70B model (needs nuance)."""
        eos = EmotionalOperatingState(
            session_depth=0.5, trust_level=0.8, emotional_stability=0.8, distress_level=0.3,
            receptiveness=Receptiveness(challenge=0.5)
        )
        ctx = AgentContext(eos=eos, user_text="test", user_name="Amiru")
        with patch("app.agents.challenge_agent.get_groq_client", return_value=mock_groq):
            result = await agent.run(ctx)
        assert result.metadata["llm_tier"] == "70B"

    def test_system_prompt_v3_one_question_only(self, agent: ChallengeAgent) -> None:
        """SYSTEM.md §5.6: One question only."""
        eos = EmotionalOperatingState()
        ctx = AgentContext(eos=eos, user_text="test", user_name="Amiru")
        prompt = agent._build_system_prompt_v3(ctx)
        assert "ONE Socratic question" in prompt
        assert "One question only" in prompt

    def test_system_prompt_v3_gentle_curious(self, agent: ChallengeAgent) -> None:
        """SYSTEM.md §5.6: Gently curious, not aggressive."""
        eos = EmotionalOperatingState()
        ctx = AgentContext(eos=eos, user_text="test", user_name="Amiru")
        prompt = agent._build_system_prompt_v3(ctx)
        assert "gently" in prompt.lower()
        assert "not aggressive" in prompt.lower()

    def test_system_prompt_v3_frame_as_exploration(self, agent: ChallengeAgent) -> None:
        """SYSTEM.md §5.6: Frame as exploration, not correction."""
        eos = EmotionalOperatingState()
        ctx = AgentContext(eos=eos, user_text="test", user_name="Amiru")
        prompt = agent._build_system_prompt_v3(ctx)
        assert "exploration, not correction" in prompt
        assert "I'm wondering" in prompt or "What if" in prompt

    def test_system_prompt_v3_no_answer(self, agent: ChallengeAgent) -> None:
        """SYSTEM.md §5.6: Do NOT give the answer. Just ask."""
        eos = EmotionalOperatingState()
        ctx = AgentContext(eos=eos, user_text="test", user_name="Amiru")
        prompt = agent._build_system_prompt_v3(ctx)
        assert "Do NOT give the answer" in prompt
        assert "Just ask" in prompt

    def test_system_prompt_v3_no_forbidden_phrases(self, agent: ChallengeAgent) -> None:
        """SYSTEM.md §5.6: No forbidden phrases."""
        eos = EmotionalOperatingState()
        ctx = AgentContext(eos=eos, user_text="test", user_name="Amiru")
        prompt = agent._build_system_prompt_v3(ctx)
        assert "NEVER use" in prompt
        assert "I understand your feelings" in prompt

    def test_system_prompt_v3_max_25_words(self, agent: ChallengeAgent) -> None:
        """SYSTEM.md §5.6: One sentence. Max 25 words."""
        eos = EmotionalOperatingState()
        ctx = AgentContext(eos=eos, user_text="test", user_name="Amiru")
        prompt = agent._build_system_prompt_v3(ctx)
        assert "Max 25 words" in prompt

    def test_system_prompt_v3_includes_distortion_context(self, agent: ChallengeAgent) -> None:
        """SYSTEM.md §5.6: Uses distortion_label from distortion_agent."""
        eos = EmotionalOperatingState()
        ctx = AgentContext(eos=eos, user_text="test", user_name="Amiru")
        prompt = agent._build_system_prompt_v3(ctx)
        assert "distortion" in prompt.lower()

    def test_max_tokens_80(self, agent: ChallengeAgent) -> None:
        assert agent.max_tokens == 80

    def test_not_always_runs(self, agent: ChallengeAgent) -> None:
        assert agent.always_runs is False
        assert agent.name == "challenge"
