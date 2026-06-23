"""Unit tests for Empathy Agent — MindLens v3 SYSTEM.md §5.4"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.agents.empathy_agent import EmpathyAgent, FORBIDDEN_PHRASES
from app.core.emotional_os import AgeGroup, EmotionalOperatingState, Modality
from app.agents.base_agent import AgentContext


class TestEmpathyAgent:
    """Validate empathy agent v3 behaviour — the most critical agent."""

    @pytest.fixture
    def agent(self) -> EmpathyAgent:
        return EmpathyAgent()

    @pytest.fixture
    def mock_groq(self) -> MagicMock:
        mock = MagicMock()
        mock.chat = AsyncMock(return_value=MagicMock(
            text="Hey Amiru, it sounds like you're really stressed about the exam. What's making it feel so overwhelming right now?\n\nWhen you're ready: music, breathing, journaling, or just talking — what do you need?",
            model_used="llama-3.1-8b-instant",
            tokens_used=45,
            latency_ms=120.0,
            finish_reason="stop",
        ))
        return mock

    # -----------------------------------------------------------------------
    # Tier selection
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_always_runs(self, agent: EmpathyAgent) -> None:
        assert agent.always_runs is True
        assert agent.name == "empathy"

    @pytest.mark.asyncio
    async def test_uses_8b_for_low_distress(self, agent: EmpathyAgent, mock_groq: MagicMock) -> None:
        """Distress < 0.5 → 8B model (SYSTEM.md §5.4)."""
        eos = EmotionalOperatingState(distress_level=0.3)
        ctx = AgentContext(eos=eos, user_text="I feel okay today.", user_name="Amiru")
        with patch("app.agents.empathy_agent.get_groq_client", return_value=mock_groq):
            result = await agent.run(ctx)
        assert result.metadata["llm_tier"] == "8B"

    @pytest.mark.asyncio
    async def test_uses_70b_for_high_distress(self, agent: EmpathyAgent, mock_groq: MagicMock) -> None:
        """Distress >= 0.5 → 70B model (SYSTEM.md §5.4)."""
        eos = EmotionalOperatingState(distress_level=0.6)
        ctx = AgentContext(eos=eos, user_text="I feel terrible.", user_name="Amiru")
        with patch("app.agents.empathy_agent.get_groq_client", return_value=mock_groq):
            result = await agent.run(ctx)
        assert result.metadata["llm_tier"] == "70B"

    @pytest.mark.asyncio
    async def test_uses_70b_for_crisis(self, agent: EmpathyAgent, mock_groq: MagicMock) -> None:
        """Distress >= 0.5 → 70B model even in crisis."""
        eos = EmotionalOperatingState(distress_level=0.95)
        ctx = AgentContext(eos=eos, user_text="I can't take it anymore.", user_name="Amiru")
        with patch("app.agents.empathy_agent.get_groq_client", return_value=mock_groq):
            result = await agent.run(ctx)
        assert result.metadata["llm_tier"] == "70B"

    # -----------------------------------------------------------------------
    # Prompt content
    # -----------------------------------------------------------------------

    def test_system_prompt_v3_includes_name(self, agent: EmpathyAgent) -> None:
        eos = EmotionalOperatingState()
        ctx = AgentContext(eos=eos, user_text="test", user_name="Amiru")
        prompt = agent._build_system_prompt_v3(ctx)
        assert "Amiru" in prompt
        assert "MindLens" in prompt
        assert "You are NOT a therapist" in prompt

    def test_system_prompt_v3_includes_age_group(self, agent: EmpathyAgent) -> None:
        eos = EmotionalOperatingState(age_group=AgeGroup.TEEN)
        ctx = AgentContext(eos=eos, user_text="test", user_name="Amiru")
        prompt = agent._build_system_prompt_v3(ctx)
        assert "teen" in prompt.lower()
        assert "Age group: teen" in prompt

    def test_system_prompt_v3_includes_people_graph(self, agent: EmpathyAgent) -> None:
        from app.core.emotional_os import PeopleGraph
        eos = EmotionalOperatingState(
            people_graph=[PeopleGraph(name="Ravi", relationship="best friend")]
        )
        ctx = AgentContext(eos=eos, user_text="test", user_name="Amiru")
        prompt = agent._build_system_prompt_v3(ctx)
        assert "Ravi" in prompt
        assert "best friend" in prompt

    def test_system_prompt_v3_high_distress_no_choices(self, agent: EmpathyAgent) -> None:
        """Distress >= 0.8: pure validation, no choices (SYSTEM.md §5.4 Rule 10)."""
        eos = EmotionalOperatingState(distress_level=0.85)
        ctx = AgentContext(eos=eos, user_text="test", user_name="Amiru")
        prompt = agent._build_system_prompt_v3(ctx)
        assert "NO choices" in prompt or "No choices" in prompt or "pure validation" in prompt

    def test_system_prompt_v3_low_distress_has_choices(self, agent: EmpathyAgent) -> None:
        """Distress < 0.8: end with choice (SYSTEM.md §5.4 Rule 5)."""
        eos = EmotionalOperatingState(distress_level=0.3)
        ctx = AgentContext(eos=eos, user_text="test", user_name="Amiru")
        prompt = agent._build_system_prompt_v3(ctx)
        assert "music, breathing, journaling" in prompt

    def test_system_prompt_v3_has_forbidden_phrases_warning(self, agent: EmpathyAgent) -> None:
        """Prompt instructs LLM to never use forbidden phrases."""
        eos = EmotionalOperatingState()
        ctx = AgentContext(eos=eos, user_text="test", user_name="Amiru")
        prompt = agent._build_system_prompt_v3(ctx)
        assert "NEVER use" in prompt
        for phrase in FORBIDDEN_PHRASES[:3]:
            assert phrase in prompt

    def test_system_prompt_v3_max_5_sentences(self, agent: EmpathyAgent) -> None:
        """Prompt instructs max 3-5 sentences (SYSTEM.md §5.4 Rule 6)."""
        eos = EmotionalOperatingState()
        ctx = AgentContext(eos=eos, user_text="test", user_name="Amiru")
        prompt = agent._build_system_prompt_v3(ctx)
        assert "3-5 sentences" in prompt

    def test_system_prompt_v3_ask_question_first(self, agent: EmpathyAgent) -> None:
        """Prompt instructs to ask one question before advice (SYSTEM.md §5.4 Rule 2)."""
        eos = EmotionalOperatingState()
        ctx = AgentContext(eos=eos, user_text="test", user_name="Amiru")
        prompt = agent._build_system_prompt_v3(ctx)
        assert "ONE good follow-up question" in prompt

    def test_system_prompt_v3_people_graph_reference(self, agent: EmpathyAgent) -> None:
        """Prompt instructs to reference people by name if relevant (SYSTEM.md §5.4 Rule 3)."""
        eos = EmotionalOperatingState()
        ctx = AgentContext(eos=eos, user_text="test", user_name="Amiru")
        prompt = agent._build_system_prompt_v3(ctx)
        assert "reference them by name" in prompt

    def test_system_prompt_v3_no_diagnose(self, agent: EmpathyAgent) -> None:
        """Prompt includes no-diagnose instruction."""
        eos = EmotionalOperatingState()
        ctx = AgentContext(eos=eos, user_text="test", user_name="Amiru")
        prompt = agent._build_system_prompt_v3(ctx)
        assert "NOT a therapist" in prompt

    def test_system_prompt_v3_teen_tone(self, agent: EmpathyAgent) -> None:
        """Teen age group gets casual tone instructions."""
        eos = EmotionalOperatingState(age_group=AgeGroup.TEEN)
        ctx = AgentContext(eos=eos, user_text="test", user_name="Amiru")
        prompt = agent._build_system_prompt_v3(ctx)
        assert "casual, relatable language" in prompt

    def test_system_prompt_v3_adult_tone(self, agent: EmpathyAgent) -> None:
        """Adult age group gets deeper tone instructions."""
        eos = EmotionalOperatingState(age_group=AgeGroup.ADULT)
        ctx = AgentContext(eos=eos, user_text="test", user_name="Amiru")
        prompt = agent._build_system_prompt_v3(ctx)
        assert "deeper, more structured language" in prompt

    def test_system_prompt_v3_session_depth_early(self, agent: EmpathyAgent) -> None:
        """Early session (depth < 0.2): no advice on first response (SYSTEM.md §5.4 Rule 9)."""
        eos = EmotionalOperatingState(session_depth=0.1)
        ctx = AgentContext(eos=eos, user_text="test", user_name="Amiru")
        prompt = agent._build_system_prompt_v3(ctx)
        assert "Do NOT give advice" in prompt or "not give advice" in prompt.lower()

    # -----------------------------------------------------------------------
    # Post-processing
    # -----------------------------------------------------------------------

    def test_strip_forbidden_removes_phrases(self, agent: EmpathyAgent) -> None:
        """Defensive: forbidden phrases are stripped from output."""
        text = "I understand your feelings, and that must be hard. But I'm here."
        cleaned = agent._strip_forbidden(text)
        assert "I understand your feelings" not in cleaned
        assert "That must be hard" not in cleaned
        assert "I'm here" in cleaned  # Non-forbidden part preserved

    def test_max_tokens(self, agent: EmpathyAgent) -> None:
        assert agent.max_tokens == 200

    # -----------------------------------------------------------------------
    # User prompt
    # -----------------------------------------------------------------------

    def test_user_prompt_v3(self, agent: EmpathyAgent) -> None:
        eos = EmotionalOperatingState()
        ctx = AgentContext(eos=eos, user_text="I feel anxious about my exam.", user_name="Amiru")
        prompt = agent._build_user_prompt_v3(ctx)
        assert "anxious about my exam" in prompt

    @pytest.mark.asyncio
    async def test_run_returns_output(self, agent: EmpathyAgent, mock_groq: MagicMock) -> None:
        eos = EmotionalOperatingState()
        ctx = AgentContext(eos=eos, user_text="I feel anxious.", user_name="Amiru")
        with patch("app.agents.empathy_agent.get_groq_client", return_value=mock_groq):
            result = await agent.run(ctx)
        assert result.agent_name == "empathy"
        assert result.text != ""
        assert "tokens_used" in result.metadata
