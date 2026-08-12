"""Unit tests for Personality Agent — MindLens v3 SYSTEM.md §5.14."""

from __future__ import annotations

import pytest
from app.agents.base_agent import AgentContext
from app.agents.personality_agent import (
    SOCIAL_DRAIN_KEYWORDS,
    SOCIAL_POSITIVE_KEYWORDS,
    SOLO_POSITIVE_KEYWORDS,
    PersonalityAgent,
)
from app.core.emotional_os import EmotionalOperatingState


class TestPersonalityAgent:
    """Validate personality agent v3 — RULE-BASED, no LLM."""

    @pytest.fixture
    def agent(self) -> PersonalityAgent:
        return PersonalityAgent()

    # -----------------------------------------------------------------------
    # Core rule: no LLM
    # -----------------------------------------------------------------------

    def test_zero_llm(self, agent: PersonalityAgent) -> None:
        """SYSTEM.md §5.14: Uses NO LLM. Rule-based scoring only."""
        assert agent.llm_tier == "none"
        assert agent.max_tokens == 0

    def test_not_always_runs(self, agent: PersonalityAgent) -> None:
        assert agent.always_runs is False
        assert agent.name == "personality"

    # -----------------------------------------------------------------------
    # Gating: no indicators detected
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_skips_when_no_indicators(self, agent: PersonalityAgent) -> None:
        """No social/solo keywords → skip."""
        eos = EmotionalOperatingState(introvert_score=0.5)
        ctx = AgentContext(eos=eos, user_text="I feel okay today.", user_name="Amiru")
        result = await agent.run(ctx)
        assert result.metadata["skipped"] is True
        assert result.metadata["reason"] == "no personality indicators detected"
        assert result.metadata["llm_tier"] == "none"
        assert result.text == ""

    # -----------------------------------------------------------------------
    # Social positive → extrovert score increases
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_social_positive_increases_extroversion(self, agent: PersonalityAgent) -> None:
        """Mentioning social activities positively → +0.05."""
        eos = EmotionalOperatingState(introvert_score=0.5)
        ctx = AgentContext(eos=eos, user_text="I had a great time hanging out with friends today.", user_name="Amiru")
        result = await agent.run(ctx)
        assert result.metadata["skipped"] is not True
        assert result.metadata["delta"] == 0.05
        # EMA: 0.8*0.50 + 0.2*(0.50+0.05) = 0.51 — the observation moves the
        # standing score by a fifth of its raw size, not all of it.
        assert result.metadata["introvert_score"] == pytest.approx(0.51)
        assert "social_positive" in str(result.metadata["reasons"])

    # -----------------------------------------------------------------------
    # Solo preference → introvert score decreases
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_solo_preference_decreases_extroversion(self, agent: PersonalityAgent) -> None:
        """Mentioning solo activities → -0.05."""
        eos = EmotionalOperatingState(introvert_score=0.5)
        ctx = AgentContext(eos=eos, user_text="I need some alone time to recharge.", user_name="Amiru")
        result = await agent.run(ctx)
        assert result.metadata["delta"] == -0.05
        assert result.metadata["introvert_score"] == pytest.approx(0.49)
        assert "solo_preference" in str(result.metadata["reasons"])

    # -----------------------------------------------------------------------
    # Social drain → introvert score decreases
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_social_drain_decreases_extroversion(self, agent: PersonalityAgent) -> None:
        """Mentioning social drain → -0.05."""
        eos = EmotionalOperatingState(introvert_score=0.5)
        ctx = AgentContext(eos=eos, user_text="People are so draining after work.", user_name="Amiru")
        result = await agent.run(ctx)
        assert result.metadata["delta"] == -0.05
        assert result.metadata["introvert_score"] == pytest.approx(0.49)
        assert "social_drain" in str(result.metadata["reasons"])

    # -----------------------------------------------------------------------
    # Score capping
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_score_capped_at_0_1(self, agent: PersonalityAgent) -> None:
        """Score cannot go below 0.1."""
        # At the floor the smoothed value (0.09) would dip under it.
        eos = EmotionalOperatingState(introvert_score=0.1)
        ctx = AgentContext(eos=eos, user_text="I love being alone by myself.", user_name="Amiru")
        result = await agent.run(ctx)
        assert result.metadata["introvert_score"] == 0.1
        assert result.metadata["delta"] == -0.05

    @pytest.mark.asyncio
    async def test_score_capped_at_0_9(self, agent: PersonalityAgent) -> None:
        """Score cannot go above 0.9."""
        eos = EmotionalOperatingState(introvert_score=0.9)
        ctx = AgentContext(eos=eos, user_text="I had fun at a party with friends.", user_name="Amiru")
        result = await agent.run(ctx)
        assert result.metadata["introvert_score"] == 0.9
        assert result.metadata["delta"] == 0.05

    # -----------------------------------------------------------------------
    # Keyword coverage
    # -----------------------------------------------------------------------

    def test_social_positive_keywords_not_empty(self, agent: PersonalityAgent) -> None:
        assert len(SOCIAL_POSITIVE_KEYWORDS) > 0

    def test_solo_positive_keywords_not_empty(self, agent: PersonalityAgent) -> None:
        assert len(SOLO_POSITIVE_KEYWORDS) > 0

    def test_social_drain_keywords_not_empty(self, agent: PersonalityAgent) -> None:
        assert len(SOCIAL_DRAIN_KEYWORDS) > 0

    # -----------------------------------------------------------------------
    # Score update metadata
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_returns_score_update(self, agent: PersonalityAgent) -> None:
        eos = EmotionalOperatingState(introvert_score=0.5)
        ctx = AgentContext(eos=eos, user_text="I went to a party with friends and had fun.", user_name="Amiru")
        result = await agent.run(ctx)
        assert "score_update" in result.metadata
        assert result.metadata["score_update"]["introvert_score"] == pytest.approx(0.51)
        assert result.metadata["score_update"]["previous_score"] == 0.5
        assert result.metadata["score_update"]["observed"] == pytest.approx(0.55)
        assert result.metadata["score_update"]["delta"] == 0.05
        assert "rule_based" in result.metadata
        assert result.metadata["rule_based"] is True

    # -----------------------------------------------------------------------
    # No external API calls
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_no_api_calls_made(self, agent: PersonalityAgent) -> None:
        """SYSTEM.md §5.14: Rule-based, zero external calls."""
        eos = EmotionalOperatingState(introvert_score=0.5)
        ctx = AgentContext(eos=eos, user_text="I love hanging out with friends.", user_name="Amiru")
        # Run without any mocking — proves no external API is called
        result = await agent.run(ctx)
        assert result is not None
        assert result.metadata["llm_tier"] == "none"

    # -----------------------------------------------------------------------
    # T2 — smoothing behaviour
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_one_message_cannot_flip_a_long_standing_profile(
        self, agent: PersonalityAgent
    ) -> None:
        """A single party does not make a settled introvert an extrovert."""
        eos = EmotionalOperatingState(introvert_score=0.15)
        ctx = AgentContext(
            eos=eos,
            user_text="I had fun at a party with friends.",
            user_name="Amiru",
        )
        result = await agent.run(ctx)
        # Moves toward extroversion, but stays unmistakably introvert-leaning.
        assert result.metadata["introvert_score"] == pytest.approx(0.16)
        assert result.metadata["introvert_score"] < 0.4

    @pytest.mark.asyncio
    async def test_repeated_evidence_does_shift_the_profile(
        self, agent: PersonalityAgent
    ) -> None:
        """Smoothing slows the profile down; it must not freeze it."""
        score = 0.5
        for _ in range(30):
            eos = EmotionalOperatingState(introvert_score=score)
            ctx = AgentContext(
                eos=eos,
                user_text="I need some alone time to recharge.",
                user_name="Amiru",
            )
            score = (await agent.run(ctx)).metadata["introvert_score"]

        assert score < 0.4, "sustained solo preference never reached RoutineAgent's branch"

    @pytest.mark.asyncio
    async def test_skipped_turn_reports_the_unchanged_score(
        self, agent: PersonalityAgent
    ) -> None:
        """A turn with no indicators must not report a drift toward 0.5."""
        eos = EmotionalOperatingState(introvert_score=0.22)
        ctx = AgentContext(eos=eos, user_text="I feel okay today.", user_name="Amiru")
        result = await agent.run(ctx)
        assert result.metadata["skipped"] is True
        assert result.metadata["introvert_score"] == 0.22
