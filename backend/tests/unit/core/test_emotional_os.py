"""Unit tests for EmotionalOperatingState Pydantic model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.emotional_os import EmotionalOperatingState, InterventionReceptiveness


class TestInterventionReceptiveness:
    """Validate InterventionReceptiveness sub-model."""

    def test_default_values(self) -> None:
        """All fields default to 0.5 except challenge (0.0)."""
        r = InterventionReceptiveness()
        assert r.music == 0.5
        assert r.journaling == 0.5
        assert r.challenge == 0.0
        assert r.grounding == 0.5
        assert r.breathing == 0.5
        assert r.routine == 0.5
        assert r.social_support == 0.5

    def test_range_enforced(self) -> None:
        """Values must be 0.0–1.0."""
        with pytest.raises(ValidationError):
            InterventionReceptiveness(music=1.5)

    def test_negative_rejected(self) -> None:
        """Negative values rejected."""
        with pytest.raises(ValidationError):
            InterventionReceptiveness(journaling=-0.1)


class TestEmotionalOperatingState:
    """Validate EmotionalOperatingState construction and behavior."""

    def test_minimal_construction(self) -> None:
        """EOS builds with all defaults."""
        eos = EmotionalOperatingState()
        assert eos.surface_emotion == "neutral"
        assert eos.core_emotion == "neutral"
        assert eos.distress_level == 0.5
        assert eos.trust_level == 0.3
        assert eos.valence == "neutral"
        assert eos.modality == "CBT"

    def test_full_construction(self) -> None:
        """EOS builds with all fields."""
        eos = EmotionalOperatingState(
            surface_emotion="anxiety",
            core_emotion="fear",
            suppressed_emotion="grief",
            emotional_stability=0.2,
            mental_fatigue=0.8,
            social_energy=0.3,
            distress_level=0.9,
            trust_level=0.6,
            attachment_style="anxious",
            valence="negative",
            modality="DBT",
            run_mindfulness=True,
            session_depth=0.7,
            alliance_score=0.5,
        )
        assert eos.modality == "DBT"
        assert eos.run_mindfulness is True
        assert eos.attachment_style == "anxious"

    def test_distress_range_enforced(self) -> None:
        """distress_level must be 0.0–1.0."""
        with pytest.raises(ValidationError):
            EmotionalOperatingState(distress_level=1.5)

    def test_negative_distress_rejected(self) -> None:
        """distress_level cannot be negative."""
        with pytest.raises(ValidationError):
            EmotionalOperatingState(distress_level=-0.1)

    def test_invalid_attachment_rejected(self) -> None:
        """attachment_style must be one of the Literal values."""
        with pytest.raises(ValidationError):
            EmotionalOperatingState(attachment_style="invalid")

    def test_invalid_modality_rejected(self) -> None:
        """modality must be one of the Literal values."""
        with pytest.raises(ValidationError):
            EmotionalOperatingState(modality="Invalid")

    def test_to_dict_roundtrip(self) -> None:
        """to_dict() → from_dict() preserves data."""
        eos = EmotionalOperatingState(
            surface_emotion="joy",
            core_emotion="contentment",
            distress_level=0.2,
        )
        dumped = eos.to_dict()
        assert isinstance(dumped, dict)
        assert dumped["surface_emotion"] == "joy"

        restored = EmotionalOperatingState.from_dict(dumped)
        assert restored.surface_emotion == "joy"
        assert restored.distress_level == 0.2

    def test_receptiveness_nested(self) -> None:
        """InterventionReceptiveness is nested correctly."""
        eos = EmotionalOperatingState()
        assert isinstance(eos.receptiveness, InterventionReceptiveness)
        assert eos.receptiveness.music == 0.5