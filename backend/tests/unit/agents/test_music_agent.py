"""Unit tests for Music Agent."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.agents.music_agent import MusicAgent
from app.core.emotional_os import EmotionalOperatingState


class TestMusicAgent:
    """Validate music agent behaviour."""

    @pytest.fixture
    def agent(self) -> MusicAgent:
        return MusicAgent()

    @pytest.fixture
    def mock_groq(self) -> MagicMock:
        mock = MagicMock()
        mock.chat = AsyncMock(return_value=MagicMock(
            text="Try slow ambient music with a steady beat. It can help regulate your nervous system.",
            model_used="llama-3.1-8b-instant",
            tokens_used=20,
            latency_ms=95.0,
            finish_reason="stop",
        ))
        return mock

    @pytest.mark.asyncio
    async def test_run(self, agent: MusicAgent, agent_context: EmotionalOperatingState, mock_groq: MagicMock) -> None:
        with patch("app.agents.music_agent.get_groq_client", return_value=mock_groq):
            result = await agent.run(agent_context)
        assert result.agent_name == "music"
        assert len(result.text) > 0

    @pytest.mark.asyncio
    async def test_system_prompt_maps_emotion(self, agent: MusicAgent, agent_context: EmotionalOperatingState) -> None:
        prompt = agent._build_system_prompt(agent_context)
        assert "MUSIC TYPE" in prompt
        assert "ambient" in prompt.lower() or "binaural" in prompt.lower() or "instrumental" in prompt.lower()

    def test_max_tokens(self, agent: MusicAgent) -> None:
        assert agent.max_tokens == 200
