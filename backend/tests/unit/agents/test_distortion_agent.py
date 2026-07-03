"""Unit tests for Distortion Agent."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

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
        with patch("app.agents.distortion_agent.get_groq_client", return_value=mock_groq):
            result = await agent.run(stable_agent_context)
        assert result.agent_name == "distortion"
        assert "all-or-nothing" in result.text.lower() or "thinking" in result.text.lower()

    def test_max_tokens(self, agent: DistortionAgent) -> None:
        assert agent.max_tokens == 0
