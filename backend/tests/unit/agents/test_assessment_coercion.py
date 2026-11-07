"""Hosted models answer magnitudes and booleans in words, not JSON types.

These are regression tests for the silent-failure class where `float("high")`
raised, the except returned 0.0, and every downstream consumer read "no
distress" — no safety review, no DBT, a flat mood history, and a Progress page
reporting 10.0/10 for someone in real trouble.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.agents.hosted_graph import ROUTES, HostedGraphOrchestrator, _normalize_route
from app.agents.hosted_graph_state import _flag, _number


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (0.75, 0.75),
        ("0.75", 0.75),
        ("75%", 0.75),
        ("3/4", 0.75),
        ("high", 0.8),
        ("very high", 0.9),
        ("moderately high", 0.8),
        ("severe", 0.9),
        ("low", 0.2),
        ("none", 0.0),
        ("8", 1.0),
    ],
)
def test_number_coerces_a_models_vocabulary(raw, expected) -> None:
    assert _number(raw) == pytest.approx(expected)


@pytest.mark.parametrize("raw", ["", "   ", None, [], {}, "yesterday", True])
def test_number_keeps_the_callers_default_when_genuinely_unparseable(raw) -> None:
    assert _number(raw, 0.42) == 0.42


def test_a_word_is_not_treated_as_unparseable() -> None:
    assert _number("high", 0.0) == 0.8


@pytest.mark.parametrize(("raw", "expected"), [("false", False), ("no", False), ("none", False)])
def test_the_word_false_never_becomes_true(raw, expected) -> None:
    assert _flag(raw, True) is expected


@pytest.mark.parametrize(("raw", "expected"), [("true", True), ("yes", True), ("high", True)])
def test_the_word_true_becomes_true(raw, expected) -> None:
    assert _flag(raw, False) is expected


def test_an_unknown_flag_word_falls_back_to_the_default() -> None:
    assert _flag("moderate", False) is False
    assert _flag("moderate", True) is True


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("empathy", "empathy"),
        ("self_help", "journaling"),
        ("supportive", "empathy"),
        ("none", "empathy"),
        ("CBT", "challenge"),
        ("grounding", "mindfulness"),
        ("coping", "routine"),
        ("something_invented", "empathy"),
        (None, "empathy"),
    ],
)
def test_route_normalisation(raw, expected) -> None:
    route = _normalize_route(raw)
    assert route in ROUTES
    assert route == expected


async def _run_with_assessment(assessment: dict) -> dict:
    client = MagicMock()
    payload = json.dumps(assessment)
    client.chat = AsyncMock(
        side_effect=[
            MagicMock(text=payload),
            MagicMock(text="That sounds heavy. What part is loudest right now?"),
            MagicMock(text='{"approved": true, "replacement": ""}'),
        ]
    )
    with patch("app.agents.hosted_graph.get_groq_client", return_value=client), patch(
        "app.agents.hosted_graph.get_hosted_retriever"
    ) as retriever:
        retriever.return_value.retrieve.return_value = []
        graph = HostedGraphOrchestrator()
        return await graph.run_full_pipeline(
            "I haven't slept in three days and nothing I do feels like it matters"
        )


@pytest.mark.asyncio
async def test_a_verbal_distress_score_reaches_the_eos_and_the_review_branch() -> None:
    result = await _run_with_assessment(
        {
            "surface_emotion": "despair",
            "surface_confidence": "high",
            "core_emotion": "hopelessness",
            "distress_level": "high",
            "mental_fatigue": "severe",
            "modality": "DBT",
            "crisis_risk": "false",
            "route": "self_help",
            "review_required": "false",
        }
    )
    assert result["eos"]["distress_level"] == pytest.approx(0.8)
    assert result["eos"]["surface_confidence"] == pytest.approx(0.8)
    assert result["eos"]["modality"] == "DBT"
    assert result["crisis_flag"] is False
    assert "review" in result["telemetry"]["graph"]["nodes"]
    assert result["telemetry"]["graph"]["route"] == "journaling"


@pytest.mark.asyncio
async def test_a_low_verbal_score_does_not_invent_a_review() -> None:
    result = await _run_with_assessment(
        {
            "surface_emotion": "stress",
            "distress_level": "low",
            "crisis_risk": "false",
            "route": "empathy",
            "review_required": "false",
        }
    )
    assert result["eos"]["distress_level"] == pytest.approx(0.2)
    assert "review" not in result["telemetry"]["graph"]["nodes"]
