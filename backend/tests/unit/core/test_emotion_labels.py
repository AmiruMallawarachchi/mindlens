# tests/unit/core/test_emotion_labels.py
"""Unit tests for go-emotions taxonomy constants."""

from __future__ import annotations

from app.core.emotion_labels import (
    EMOTION_LABELS,
    EMOTION_SEVERITY_WEIGHTS,
    NEGATIVE_EMOTIONS,
    POSITIVE_EMOTIONS,
    get_emotion_name,
    is_negative,
    severity_weight,
)


class TestEmotionLabels:
    """Validate the 28-class mapping and groupings."""

    def test_all_28_labels_present(self) -> None:
        """LABEL_0 through LABEL_27 must all exist."""
        for i in range(28):
            key = f"LABEL_{i}"
            assert key in EMOTION_LABELS, f"{key} missing from EMOTION_LABELS"

    def test_no_duplicate_names(self) -> None:
        """All canonical names must be unique."""
        names = list(EMOTION_LABELS.values())
        assert len(names) == len(set(names))

    def test_negative_emotions_subset(self) -> None:
        """NEGATIVE_EMOTIONS must only contain valid label names."""
        for emotion in NEGATIVE_EMOTIONS:
            assert emotion in EMOTION_LABELS.values(), f"{emotion} not in labels"

    def test_positive_emotions_subset(self) -> None:
        """POSITIVE_EMOTIONS must only contain valid label names."""
        for emotion in POSITIVE_EMOTIONS:
            assert emotion in EMOTION_LABELS.values(), f"{emotion} not in labels"

    def test_severity_weights_for_all_negatives(self) -> None:
        """Every negative emotion should have a severity weight defined."""
        for emotion in NEGATIVE_EMOTIONS:
            assert emotion in EMOTION_SEVERITY_WEIGHTS, f"{emotion} missing severity"

    def test_severity_range(self) -> None:
        """All severity weights must be 0.0–1.0."""
        for weight in EMOTION_SEVERITY_WEIGHTS.values():
            assert 0.0 <= weight <= 1.0

    def test_get_emotion_name(self) -> None:
        """Mapping from LABEL ID to name works."""
        assert get_emotion_name("LABEL_0") == "admiration"
        assert get_emotion_name("LABEL_25") == "sadness"
        assert get_emotion_name("UNKNOWN") == "unknown"

    def test_is_negative(self) -> None:
        """Negative detection works."""
        assert is_negative("sadness") is True
        assert is_negative("joy") is False

    def test_severity_weight(self) -> None:
        """Severity lookup works; unknown emotions default to 0.0."""
        assert severity_weight("grief") == 1.0
        assert severity_weight("joy") == 0.0
