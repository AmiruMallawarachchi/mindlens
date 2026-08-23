"""Unit tests for Distortion Agent."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.agents.distortion_agent import DistortionAgent
from app.core.emotional_os import EmotionalOperatingState


class TestDistortionAgent:
    """Validate distortion agent behaviour."""

    @pytest.fixture
    def agent(self) -> DistortionAgent:
        return DistortionAgent()

    @pytest.fixture
    def mock_groq(self) -> MagicMock:
        mock = MagicMock()
        mock.chat = AsyncMock(return_value=MagicMock(
            text="That sounds like all-or-nothing thinking. What's the evidence?",
            model_used="llama-3.1-8b-instant",
            tokens_used=15,
            latency_ms=100.0,
            finish_reason="stop",
        ))
        return mock

    @pytest.mark.asyncio
    async def test_run(self, agent: DistortionAgent, stable_agent_context: EmotionalOperatingState, mock_groq: MagicMock) -> None:
        stable_agent_context.user_text = "I always fail, so everything is ruined."
        result = await agent.run(stable_agent_context)
        assert result.agent_name == "distortion"
        assert result.metadata["distortion_label"] in {
            "all_or_nothing",
            "catastrophizing",
        }
        mock_groq.chat.assert_not_awaited()

    def test_max_tokens(self, agent: DistortionAgent) -> None:
        assert agent.max_tokens == 0

    @pytest.mark.asyncio
    async def test_no_pattern_says_nothing(
        self, agent: DistortionAgent, stable_agent_context: EmotionalOperatingState
    ) -> None:
        """A "none" finding must produce no spoken text.

        It used to return "No clear thinking pattern detected. That's okay —
        sometimes feelings are just feelings.", which the assembler then
        stapled onto empathy's reply — so telling Mindlens about two people
        you love came back with a flat clinical sentence about an absent
        thinking pattern. The label still travels in metadata for the
        challenge agent and the UI badge; only the prose is withheld.
        """
        stable_agent_context.user_text = (
            "i have a boy friend call hasanka and my moms name is Rehana"
        )
        stable_agent_context.eos.distortion_label = None
        result = await agent.run(stable_agent_context)
        assert result.metadata["distortion_label"] == "none"
        assert result.text == ""

    def test_unknown_label_says_nothing_rather_than_raising(
        self, agent: DistortionAgent
    ) -> None:
        """A label with no phrasings must not KeyError or invent an
        observation — the table is not guaranteed to cover every class the
        classifier can emit."""
        assert agent._build_explanation("some_unmapped_label", "text") == ""
        assert agent._build_explanation("none", "text") == ""
