"""Unit tests for ResponseValidator's forbidden-pattern categories.

Focused on the medication pattern: a live chat turn was blocked outright
because the reply opened with "I recommend..." about something unrelated
to medication entirely, and every reply using that ordinary phrasing was
getting the generic fallback instead of reaching the user. These pin both
directions — real medication content still blocks, ordinary supportive
phrasing doesn't.
"""

from __future__ import annotations

import pytest
from app.agents.response_validator import ResponseValidator

validator = ResponseValidator()


@pytest.mark.parametrize(
    "text",
    [
        "I recommend taking sertraline for your anxiety.",
        "You should take Xanax when you feel panicky.",
        "Maybe start taking your prescribed medication daily.",
        "Try taking 50mg of Zoloft in the morning.",
        "You could consider medication as an option.",
        "Ask your doctor for a prescription.",
        "That's a prescription of Prozac.",
        "A dosage of 20mg is typical.",
        "Have you thought about taking fluoxetine?",
    ],
)
def test_medication_pattern_still_catches_real_advice(text: str) -> None:
    report = validator.validate(text)
    assert not report.passed
    assert "medication" in report.blocked_categories
    assert report.severity == "critical"


@pytest.mark.parametrize(
    "text",
    [
        "I recommend taking a short walk to clear your head.",
        "You should take a break before the exam.",
        "Try taking a few deep breaths before you start.",
        "Start taking small steps each day, even tiny ones.",
        "I recommend journaling before bed tonight.",
        "You should take some time for yourself this weekend.",
        "I'm here with you. Tell me more.",
        "It sounds like you're treating your feelings as facts.",
    ],
)
def test_medication_pattern_does_not_false_positive_on_ordinary_phrasing(
    text: str,
) -> None:
    report = validator.validate(text)
    assert report.passed, f"false positive: {report.blocked_categories} on {text!r}"
