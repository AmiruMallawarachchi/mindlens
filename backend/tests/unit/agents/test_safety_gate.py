"""Unit tests for the Safety Gate."""

from __future__ import annotations

import pytest
from app.agents.safety_gate import (
    layer1_keyword_scan,
    safety_gate,
)


class TestSafetyGateKeywordScan:
    """Validate Layer 1 keyword scanning."""

    @pytest.mark.asyncio
    async def test_no_matches(self) -> None:
        result = await layer1_keyword_scan(
            "I had a good day at work."
        )

        assert result["triggered"] is False
        assert result["matches"] == [""]

    @pytest.mark.asyncio
    async def test_exact_match(self) -> None:
        result = await layer1_keyword_scan(
            "I want to commit suicide"
        )

        assert result["triggered"] is True
        assert len(result["matches"]) > 0

    @pytest.mark.asyncio
    async def test_case_insensitive_match(self) -> None:
        result = await layer1_keyword_scan(
            "I want to kill myself"
        )

        assert result["triggered"] is True
        assert len(result["matches"]) > 0


class TestSafetyGateEvaluate:
    """Validate overall gate behaviour."""

    @pytest.mark.asyncio
    async def test_safe_message(self) -> None:
        result = await safety_gate.evaluate(
            "I am happy today."
        )

        assert result.is_crisis is False
        assert result.layer_triggered is None
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_crisis_message(self) -> None:
        result = await safety_gate.evaluate(
            "I want to end my life"
        )

        assert result.is_crisis is True
        assert result.layer_triggered == "regex"
        assert result.confidence == 0.95

    @pytest.mark.asyncio
    async def test_suicide_phrase(self) -> None:
        result = await safety_gate.evaluate(
            "I want to die"
        )

        assert result.is_crisis is True
        assert result.layer_triggered == "regex"

    @pytest.mark.asyncio
    async def test_harm_to_others_phrase(self) -> None:
        result = await safety_gate.evaluate(
            "I want to kill someone"
        )

        assert result.is_crisis is True
        assert result.layer_triggered == "regex"

    @pytest.mark.asyncio
    async def test_hopelessness_phrase(self) -> None:
        result = await safety_gate.evaluate(
            "I feel completely hopeless"
        )

        assert result.is_crisis is True
        assert result.layer_triggered == "regex"

    @pytest.mark.asyncio
    async def test_snippet_truncation(self) -> None:
        text = "a" * 150

        result = await safety_gate.evaluate(text)

        assert len(result.user_message_snippet) == 100
