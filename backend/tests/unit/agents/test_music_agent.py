"""Unit tests for Music Agent."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from app.agents.music_agent import MusicAgent
from app.core.emotional_os import EmotionalOperatingState

ITUNES_RESULT = {
    "results": [
        {
            "trackName": "Weightless",
            "artistName": "Marconi Union",
            "previewUrl": "https://audio-ssl.itunes.apple.com/preview.m4a",
            "trackViewUrl": "https://music.apple.com/track/weightless",
        },
        {
            "trackName": "No Preview Track",
            "artistName": "Some Artist",
            "previewUrl": None,
            "trackViewUrl": "https://music.apple.com/track/no-preview",
        },
    ]
}


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

    @staticmethod
    def _mock_itunes_response(payload: dict) -> MagicMock:
        response = MagicMock()
        response.json.return_value = payload
        response.raise_for_status = MagicMock()
        return response

    @pytest.mark.asyncio
    async def test_run_returns_real_track_with_preview(
        self, agent: MusicAgent, agent_context: EmotionalOperatingState, mock_groq: MagicMock
    ) -> None:
        """The happy path: iTunes returns tracks, one with a preview URL —
        that shape must survive into the agent's output metadata unchanged,
        since the frontend plays preview_url directly."""
        with (
            patch("app.agents.music_agent.get_groq_client", return_value=mock_groq),
            patch.object(
                httpx.AsyncClient, "get", AsyncMock(return_value=self._mock_itunes_response(ITUNES_RESULT))
            ),
        ):
            result = await agent.run(agent_context)

        assert result.agent_name == "music"
        assert len(result.text) > 0
        tracks = result.metadata["tracks"]
        assert tracks[0]["name"] == "Weightless"
        assert tracks[0]["artist"] == "Marconi Union"
        assert tracks[0]["preview_url"] == "https://audio-ssl.itunes.apple.com/preview.m4a"
        # Second track genuinely has no preview in the fixture — must pass
        # through as None, not be silently dropped or defaulted to a value
        # that would render a fake play button.
        assert tracks[1]["preview_url"] is None
        assert tracks[1]["track_url"] == "https://music.apple.com/track/no-preview"

    @pytest.mark.asyncio
    async def test_run_falls_back_when_itunes_unreachable(
        self, agent: MusicAgent, agent_context: EmotionalOperatingState, mock_groq: MagicMock
    ) -> None:
        """iTunes down/network error -> static fallback, not a crashed turn."""
        with (
            patch("app.agents.music_agent.get_groq_client", return_value=mock_groq),
            patch.object(
                httpx.AsyncClient, "get", AsyncMock(side_effect=httpx.ConnectError("refused"))
            ),
        ):
            result = await agent.run(agent_context)

        assert result.agent_name == "music"
        assert len(result.metadata["tracks"]) > 0
        # Fallback tracks carry no URLs at all — the prompt must not be
        # asked to invent one for them.
        assert all("preview_url" not in t for t in result.metadata["tracks"])

    @pytest.mark.asyncio
    async def test_run_dedupes_same_track_across_releases(
        self, agent: MusicAgent, agent_context: EmotionalOperatingState, mock_groq: MagicMock
    ) -> None:
        """iTunes genuinely re-releases the same song under different
        trackIds across compilation albums — confirmed live, the card
        showed the same title/artist listed three times in a row. The
        agent must collapse those to one entry rather than pass the
        duplicates through."""
        duplicated = {
            "results": [
                {
                    "trackName": "Coffee Break",
                    "artistName": "FM STAR",
                    "previewUrl": "https://a.example/1.m4a",
                    "trackViewUrl": "https://music.apple.com/1",
                },
                {
                    "trackName": "Coffee Break",  # same title+artist, different id/album
                    "artistName": "FM STAR",
                    "previewUrl": "https://a.example/2.m4a",
                    "trackViewUrl": "https://music.apple.com/2",
                },
                {
                    "trackName": "Coffee Break",
                    "artistName": "fm star",  # case-only difference — still a duplicate
                    "previewUrl": "https://a.example/3.m4a",
                    "trackViewUrl": "https://music.apple.com/3",
                },
                {
                    "trackName": "Different Song",
                    "artistName": "Someone Else",
                    "previewUrl": "https://a.example/4.m4a",
                    "trackViewUrl": "https://music.apple.com/4",
                },
            ]
        }
        with (
            patch("app.agents.music_agent.get_groq_client", return_value=mock_groq),
            patch.object(
                httpx.AsyncClient, "get", AsyncMock(return_value=self._mock_itunes_response(duplicated))
            ),
        ):
            result = await agent.run(agent_context)

        names = [(t["name"], t["artist"]) for t in result.metadata["tracks"]]
        assert names.count(("Coffee Break", "FM STAR")) == 1
        assert ("Different Song", "Someone Else") in names
        assert len(result.metadata["tracks"]) == 2

    @pytest.mark.asyncio
    async def test_run_falls_back_when_itunes_returns_no_results(
        self, agent: MusicAgent, agent_context: EmotionalOperatingState, mock_groq: MagicMock
    ) -> None:
        with (
            patch("app.agents.music_agent.get_groq_client", return_value=mock_groq),
            patch.object(
                httpx.AsyncClient, "get", AsyncMock(return_value=self._mock_itunes_response({"results": []}))
            ),
        ):
            result = await agent.run(agent_context)

        assert len(result.metadata["tracks"]) > 0  # static fallback, not empty

    def test_system_prompt_maps_emotion_to_search_terms(
        self, agent: MusicAgent, agent_context: EmotionalOperatingState
    ) -> None:
        search_terms = {"genre": "ambient", "mood": "calm slow instrumental"}
        prompt = agent._build_music_wrapper_prompt(agent_context, "anxiety", search_terms)
        assert "ambient" in prompt.lower()
        assert "calm slow instrumental" in prompt.lower()

    def test_system_prompt_forbids_urls_and_other_platforms(
        self, agent: MusicAgent, agent_context: EmotionalOperatingState
    ) -> None:
        """Regression guard for the hallucination-bait bug: the old prompt
        handed the model 'YouTube: N/A' and then asked it for a link
        anyway. The new prompt must explicitly forbid inventing one, and
        must explicitly forbid suggesting the user connect a third-party
        platform the app doesn't integrate with."""
        prompt = agent._build_music_wrapper_prompt(agent_context, "sadness", {"genre": "acoustic", "mood": "gentle soft"})
        lower = prompt.lower()
        assert "never write a url" in lower
        # "spotify" appearing is fine — it should, inside the instruction
        # forbidding the model from mentioning it. What must NOT appear is
        # language inviting the model to suggest connecting one.
        assert "never mention spotify" in lower
        assert "connect your spotify" not in lower
        assert "connect spotify" not in lower

    def test_max_tokens(self, agent: MusicAgent) -> None:
        assert agent.max_tokens == 200
