"""Unit tests for the progress insight service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.services.progress import generate_progress_insight


def _groq(text: str) -> MagicMock:
    client = MagicMock()
    client.chat = AsyncMock(return_value=MagicMock(text=text))
    return client


class TestGenerateProgressInsight:
    @pytest.mark.asyncio
    async def test_returns_the_model_text(self) -> None:
        client = _groq("You've been showing up consistently, Amiru. That's a real win.")
        with patch("app.services.progress.get_groq_client", return_value=client):
            insight = await generate_progress_insight(
                user_name="Amiru",
                session_history=[{"emotion": "joy"}, {"emotion": "calm"}],
            )
        assert insight == "You've been showing up consistently, Amiru. That's a real win."

    @pytest.mark.asyncio
    async def test_uses_the_synthesis_tier_and_budget(self) -> None:
        """SYSTEM.md specifies 70B for pattern synthesis across sessions and
        a 350-token cap for this card."""
        client = _groq("An insight.")
        with patch("app.services.progress.get_groq_client", return_value=client):
            await generate_progress_insight(user_name="Amiru")
        kwargs = client.chat.await_args.kwargs
        assert kwargs["model_tier"] == "70B"
        assert kwargs["max_tokens"] == 350

    @pytest.mark.asyncio
    async def test_history_emotions_reach_the_prompt(self) -> None:
        client = _groq("An insight.")
        with patch("app.services.progress.get_groq_client", return_value=client):
            await generate_progress_insight(
                user_name="Amiru",
                session_history=[{"emotion": "joy"}, {"emotion": "nervousness"}],
            )
        prompt = client.chat.await_args.kwargs["user_prompt"]
        assert "joy, nervousness" in prompt
