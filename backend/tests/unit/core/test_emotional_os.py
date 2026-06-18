"""Unit tests for the Emotional Operating System (EOS)."""

from __future__ import annotations

import pytest
from app.core.emotional_os import (
    AgeGroup,
    EmotionalOperatingState,
    Modality,
    PeopleGraph,
    Receptiveness,
    create_calm_eos,
    create_crisis_eos,
    create_distressed_eos,
)


class TestEmotionalOperatingStateDefaults:
    """Validate default field values."""

    def test_default_surface_emotion(self) -> None:
        """Default surface emotion is neutral."""
        eos = EmotionalOperatingState()
        assert eos.surface_emotion == "neutral"

    def test_default_distress_level(self) -> None:
        """Default distress level is 0.5."""
        eos = EmotionalOperatingState()
        assert eos.distress_level == 0.5

    def test_default_modality(self) -> None:
        """Default modality is CBT."""
        eos = EmotionalOperatingState()
        assert eos.modality == Modality.CBT

    def test_default_age_group(self) -> None:
        """Default age group is adult."""
        eos = EmotionalOperatingState()
        assert eos.age_group == AgeGroup.ADULT

    def test_default_receptiveness(self) -> None:
        """Default receptiveness has all fields."""
        eos = EmotionalOperatingState()
        assert eos.receptiveness.music == 0.5
        assert eos.receptiveness.journaling == 0.5
        assert eos.receptiveness.challenge == 0.3
        assert eos.receptiveness.breathing == 0.5

    def test_default_session_turn_count(self) -> None:
        """Default session turn count is 0."""
        eos = EmotionalOperatingState()
        assert eos.session_turn_count == 0

    def test_default_people_graph(self) -> None:
        """Default people graph is empty list."""
        eos = EmotionalOperatingState()
        assert eos.people_graph == []


class TestEmotionalOperatingStateValidation:
    """Validate field constraints."""

    def test_distress_level_bounds(self) -> None:
        """Distress level must be between 0 and 1."""
        with pytest.raises(ValueError):
            EmotionalOperatingState(distress_level=1.5)

    def test_trust_level_bounds(self) -> None:
        """Trust level must be between 0 and 1."""
        with pytest.raises(ValueError):
            EmotionalOperatingState(trust_level=-0.5)

    def test_session_turn_count_non_negative(self) -> None:
        """Session turn count cannot be negative."""
        with pytest.raises(ValueError):
            EmotionalOperatingState(session_turn_count=-1)


class TestEmotionalOperatingStateMethods:
    """Validate helper methods."""

    def test_should_use_deep_llm_high_distress(self) -> None:
        """High distress triggers deep LLM."""
        eos = EmotionalOperatingState(distress_level=0.6)
        assert eos.should_use_deep_llm() is True

    def test_should_use_deep_llm_high_depth(self) -> None:
        """High session depth triggers deep LLM."""
        eos = EmotionalOperatingState(session_depth=0.4)
        assert eos.should_use_deep_llm() is True

    def test_should_use_deep_llm_low_values(self) -> None:
        """Low values do not trigger deep LLM."""
        eos = EmotionalOperatingState(distress_level=0.2, session_depth=0.1)
        assert eos.should_use_deep_llm() is False

    def test_is_in_crisis_high_distress(self) -> None:
        """Distress >= 0.85 is crisis."""
        eos = EmotionalOperatingState(distress_level=0.9)
        assert eos.is_in_crisis() is True

    def test_is_in_crisis_escalating(self) -> None:
        """Crisis escalating flag triggers crisis."""
        eos = EmotionalOperatingState(crisis_escalating=True)
        assert eos.is_in_crisis() is True

    def test_is_receptive_to_music(self) -> None:
        """Receptiveness check for music."""
        eos = EmotionalOperatingState(receptiveness=Receptiveness(music=0.7))
        assert eos.is_receptive_to("music") is True

    def test_is_receptive_to_low_value(self) -> None:
        """Low receptiveness returns False."""
        eos = EmotionalOperatingState(receptiveness=Receptiveness(music=0.3))
        assert eos.is_receptive_to("music") is False

    def test_get_agent_routing_decision(self) -> None:
        """Routing decision includes empathy and safety."""
        eos = EmotionalOperatingState()
        routing = eos.get_agent_routing_decision()
        assert routing["empathy_agent"] is True
        assert routing["safety_gate"] is True


class TestReceptiveness:
    """Validate Receptiveness model."""

    def test_default_values(self) -> None:
        """All fields have defaults."""
        r = Receptiveness()
        assert r.music == 0.5
        assert r.journaling == 0.5
        assert r.challenge == 0.3
        assert r.breathing == 0.5
        assert r.routine == 0.4
        assert r.practical == 0.6
        assert r.grounding == 0.5
        assert r.social_support == 0.5

    def test_custom_values(self) -> None:
        """Custom values are accepted."""
        r = Receptiveness(music=0.9, challenge=0.1)
        assert r.music == 0.9
        assert r.challenge == 0.1

    def test_bounds(self) -> None:
        """Values must be between 0 and 1."""
        with pytest.raises(ValueError):
            Receptiveness(music=1.5)


class TestPeopleGraph:
    """Validate PeopleGraph model."""

    def test_basic_creation(self) -> None:
        """Can create a PeopleGraph entry."""
        person = PeopleGraph(name="Ravi", relationship="best friend")
        assert person.name == "Ravi"
        assert person.relationship == "best friend"
        assert person.context is None

    def test_with_context(self) -> None:
        """PeopleGraph with context."""
        person = PeopleGraph(
            name="mum",
            relationship="mother",
            context="worried about results",
        )
        assert person.context == "worried about results"


class TestFactoryFunctions:
    """Validate factory functions."""

    def test_create_calm_eos(self) -> None:
        """Calm EOS has low distress."""
        eos = create_calm_eos()
        assert eos.distress_level == 0.1
        assert eos.modality == Modality.MINDFULNESS

    def test_create_distressed_eos(self) -> None:
        """Distressed EOS has high distress."""
        eos = create_distressed_eos()
        assert eos.distress_level == 0.75
        assert eos.age_group == AgeGroup.TEEN

    def test_create_crisis_eos(self) -> None:
        """Crisis EOS has very high distress."""
        eos = create_crisis_eos()
        assert eos.distress_level == 0.95
        assert eos.crisis_escalating is True

    def test_custom_session_id(self) -> None:
        """Factory accepts custom session ID."""
        eos = create_calm_eos(session_id="test-123")
        assert eos.session_id == "test-123"
