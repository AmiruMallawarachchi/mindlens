"""Unit tests for structured follow-up options."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.agents.question_options import _looks_like_a_question, _parse, build_options


class TestOptionParsing:
    """Validation is strict on purpose.

    Showing no options is always acceptable; showing wrong ones is not. So
    anything that doesn't match the shape returns None rather than being
    repaired into a half-menu.
    """

    def test_accepts_a_clean_object(self) -> None:
        assert _parse('{"options": ["Work stress", "Something at home"]}') == [
            "Work stress",
            "Something at home",
        ]

    def test_accepts_json_wrapped_in_prose_or_fences(self) -> None:
        raw = 'Sure!\n```json\n{"options": ["Yes", "Not really"]}\n```'
        assert _parse(raw) == ["Yes", "Not really"]

    @pytest.mark.parametrize(
        "raw",
        [
            "not json at all",
            '{"options": "a string not a list"}',
            '{"options": ["only one"]}',
            '{"options": ["a", "b", "c", "d", "e"]}',
            '{"options": ["fine", 42]}',
            '{"options": []}',
            '{"nope": ["a", "b"]}',
        ],
    )
    def test_rejects_anything_off_shape(self, raw: str) -> None:
        assert _parse(raw) is None

    def test_rejects_an_overlong_option(self) -> None:
        assert _parse('{"options": ["ok", "%s"]}' % ("x" * 60)) is None

    def test_dedupes_case_insensitively(self) -> None:
        """Two options saying the same thing is worse than none."""
        assert _parse('{"options": ["Yes", "yes", "No"]}') == ["Yes", "No"]

    def test_collapses_runs_of_whitespace(self) -> None:
        assert _parse('{"options": ["too   many    spaces", "fine"]}') == [
            "too many spaces",
            "fine",
        ]

    def test_rejects_a_literal_newline_inside_a_string(self) -> None:
        """That is invalid JSON, and repairing it would mean guessing."""
        raw = '{"options": ["broken' + chr(10) + 'string", "fine"]}'
        assert _parse(raw) is None


class TestQuestionGate:
    def test_only_questions_qualify(self) -> None:
        assert _looks_like_a_question("What's on your mind?") is True
        assert _looks_like_a_question("That sounds heavy.") is False


class TestBuildOptions:
    @pytest.mark.asyncio
    async def test_returns_none_without_a_question(self) -> None:
        """The cheap gate must short-circuit before any API call."""
        with patch("app.agents.question_options.get_groq_client") as client:
            assert await build_options("That sounds heavy.", "hi") is None
            client.assert_not_called()

    @pytest.mark.asyncio
    async def test_builds_a_payload_that_always_allows_other(self) -> None:
        mock = MagicMock()
        mock.chat = AsyncMock(
            return_value=MagicMock(text='{"options": ["Work", "Home"]}')
        )
        with patch("app.agents.question_options.get_groq_client", return_value=mock):
            payload = await build_options("What's weighing on you?", "im stressed")

        assert payload == {"options": ["Work", "Home"], "allow_other": True}

    @pytest.mark.asyncio
    async def test_model_failure_yields_no_options_rather_than_an_error(self) -> None:
        mock = MagicMock()
        mock.chat = AsyncMock(side_effect=RuntimeError("groq down"))
        with patch("app.agents.question_options.get_groq_client", return_value=mock):
            assert await build_options("What's weighing on you?", "hi") is None

    @pytest.mark.asyncio
    async def test_unusable_output_yields_no_options(self) -> None:
        mock = MagicMock()
        mock.chat = AsyncMock(return_value=MagicMock(text="I think maybe work?"))
        with patch("app.agents.question_options.get_groq_client", return_value=mock):
            assert await build_options("What's weighing on you?", "hi") is None
