"""Convenience constructors for common EOS test and initialization states."""

from app.core.emotional_os_model import EmotionalOperatingState
from app.core.emotional_os_types import AgeGroup, Modality, Receptiveness
def create_calm_eos(session_id: str = "test") -> EmotionalOperatingState:
    """Create an EOS for a calm user."""
    return EmotionalOperatingState(
        surface_emotion="calm",
        core_emotion="contentment",
        distress_level=0.1,
        emotional_stability=0.9,
        trust_level=0.5,
        alliance_score=0.6,
        session_depth=0.2,
        modality=Modality.MINDFULNESS,
        age_group=AgeGroup.ADULT,
        receptiveness=Receptiveness(journaling=0.6),
        session_id=session_id,
    )


def create_distressed_eos(session_id: str = "test") -> EmotionalOperatingState:
    """Create an EOS for a distressed user."""
    return EmotionalOperatingState(
        surface_emotion="anxious",
        core_emotion="fear",
        distress_level=0.75,
        emotional_stability=0.3,
        trust_level=0.4,
        alliance_score=0.5,
        session_depth=0.4,
        modality=Modality.CBT,
        age_group=AgeGroup.TEEN,
        receptiveness=Receptiveness(breathing=0.9, challenge=0.2),
        session_id=session_id,
    )


def create_crisis_eos(session_id: str = "test") -> EmotionalOperatingState:
    """Create an EOS for a user in crisis."""
    return EmotionalOperatingState(
        surface_emotion="desperate",
        core_emotion="hopelessness",
        distress_level=0.95,
        emotional_stability=0.0,
        trust_level=0.2,
        alliance_score=0.3,
        session_depth=0.8,
        modality=Modality.DBT,
        crisis_escalating=True,
        session_id=session_id,
    )

