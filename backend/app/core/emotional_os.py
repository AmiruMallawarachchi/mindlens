"""
Emotional Operating System (EOS)

Tracks and manages the user's current emotional state across multiple dimensions.
The EOS is recalculated at the end of each turn and drives agent routing.
"""

import enum
import typing
from datetime import datetime

from pydantic import BaseModel, Field


class Modality(enum.StrEnum):
    """Therapy modality in use."""

    CBT = "CBT"
    DBT = "DBT"
    ACT = "ACT"
    MINDFULNESS = "Mindfulness"
    MI = "MI"
    NARRATIVE = "Narrative"


class AgeGroup(enum.StrEnum):
    """Age-based tone adaptation."""

    TEEN = "teen"
    ADULT = "adult"


class LLMTier(enum.StrEnum):
    """Which Groq model to use."""

    FAST = "8B"
    DEEP = "70B"


class Receptiveness(BaseModel):
    """User's receptiveness to different interventions (0-1 scale)."""

    music: float = Field(default=0.5, ge=0, le=1)
    journaling: float = Field(default=0.5, ge=0, le=1)
    challenge: float = Field(default=0.3, ge=0, le=1)
    breathing: float = Field(default=0.5, ge=0, le=1)
    routine: float = Field(default=0.4, ge=0, le=1)
    practical: float = Field(default=0.6, ge=0, le=1)
    grounding: float = Field(default=0.5, ge=0, le=1)
    social_support: float = Field(default=0.5, ge=0, le=1)


class PeopleGraph(BaseModel):
    """Important people mentioned by user."""

    name: str
    relationship: str
    context: str | None = None
    mentioned_at: datetime = Field(default_factory=datetime.utcnow)


class EmotionalOperatingState(BaseModel):
    """
    Complete Emotional Operating System snapshot.
    Recalculated at the end of each turn.
    """

    # --- Core Emotional State ---
    surface_emotion: str = Field(
        default="neutral",
        description="What user expressed",
    )
    surface_confidence: float = Field(
        default=0.8,
        ge=0,
        le=1,
        description="Confidence in surface emotion classification",
    )

    core_emotion: str | None = Field(
        default=None,
        description="Underlying emotion",
    )

    suppressed_emotion: str | None = Field(
        default=None,
        description="Emotion user might be hiding",
    )

    distortion_label: str | None = Field(
        default=None,
        description="Detected cognitive distortion, when available",
    )

    # --- Distress & Stability ---
    distress_level: float = Field(
        default=0.5,
        ge=0,
        le=1,
        description="Overall distress (0=calm, 1=crisis)",
    )

    emotional_stability: float = Field(
        default=0.5,
        ge=0,
        le=1,
        description="Emotional stability",
    )

    mental_fatigue: float = Field(
        default=0.3,
        ge=0,
        le=1,
        description="Mental fatigue/burnout level",
    )

    social_energy: float = Field(
        default=0.5,
        ge=0,
        le=1,
        description="Social energy available",
    )

    # --- Relationship with System ---
    trust_level: float = Field(
        default=0.3,
        ge=0,
        le=1,
        description="User trust in MindLens",
    )

    alliance_score: float = Field(
        default=0.4,
        ge=0,
        le=1,
        description="Working alliance",
    )

    attachment_style: typing.Literal["secure", "anxious", "avoidant", "unknown"] = Field(
        default="unknown"
    )

    # --- Session Engagement ---
    session_depth: float = Field(
        default=0.0,
        ge=0,
        le=1,
        description="How deeply engaged",
    )

    session_turn_count: int = Field(
        default=0,
        ge=0,
        description="Number of turns in current session",
    )

    # --- Therapy Configuration ---
    modality: Modality = Field(
        default=Modality.CBT,
        description="Active therapy approach",
    )

    age_group: AgeGroup = Field(
        default=AgeGroup.ADULT,
        description="Age-based tone adaptation",
    )

    tone_preference: typing.Literal["gentle", "balanced", "direct"] = Field(
        default="balanced",
        description="User-set Gentle<->Direct preference (Your Mindlens studio)",
    )

    # --- Intervention Preferences ---
    receptiveness: Receptiveness = Field(
        default_factory=Receptiveness,
        description="User openness to different interventions",
    )

    # --- Context ---
    people_graph: list[PeopleGraph] = Field(
        default_factory=list,
        description="Important people mentioned by user",
    )

    last_crisis_mention: datetime | None = Field(default=None)
    crisis_escalating: bool = Field(default=False)

    # --- Legacy Routing Fields (keep for compatibility) ---
    run_distortion: bool = Field(default=False)
    run_challenge: bool = Field(default=False)
    run_music: bool = Field(default=False)
    run_routine: bool = Field(default=False)
    run_journaling: bool = Field(default=False)
    run_mindfulness: bool = Field(default=False)

    # --- Metadata ---
    valence: typing.Literal["positive", "negative", "neutral"] = Field(
        default="neutral"
    )
    calculated_at: datetime = Field(default_factory=datetime.utcnow)
    session_id: str = Field(default="unknown")

    # --- Helper Methods ---

    def should_use_deep_llm(self) -> bool:
        """Decide if we need 70B model vs 8B."""
        if self.distress_level >= 0.5:
            return True
        if self.session_depth >= 0.3:
            return True
        if self.alliance_score >= 0.7:
            return True
        return False

    def is_in_crisis(self) -> bool:
        """Crisis threshold check."""
        return self.distress_level >= 0.85 or self.crisis_escalating

    def is_receptive_to(self, intervention: str) -> bool:
        """Check if user is open to an intervention."""
        receptiveness_value = getattr(
            self.receptiveness, intervention.lower(), None
        )
        if receptiveness_value is None:
            return False
        return receptiveness_value >= 0.5

    def get_agent_routing_decision(self) -> dict[str, bool]:
        """
        Determine which agents to invoke this turn.
        Returns a dict of agent names -> should_invoke.
        """
        routing = {
            "empathy_agent": True,
            "safety_gate": True,
            "crisis_agent": self.is_in_crisis(),
            "mindfulness_agent": self.distress_level >= 0.5,
            "distortion_agent": self.modality == Modality.CBT,
            "reflection_agent": self.session_depth >= 0.3,
            "challenge_agent": (
                self.trust_level >= 0.6
                and self.emotional_stability >= 0.5
                and not self.is_in_crisis()
            ),
            "routine_agent": self.mental_fatigue >= 0.7,
            "journaling_agent": (
                self.emotional_stability >= 0.3
                and self.mental_fatigue < 0.8
                and self.is_receptive_to("journaling")
            ),
            "music_agent": (
                self.distress_level >= 0.4
                or self.is_receptive_to("music")
            ),
        }
        return routing

    def to_dict(self) -> dict:
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict) -> "EmotionalOperatingState":
        return cls(**data)


# --- Backward Compatibility Alias ---
EmotionalOS = EmotionalOperatingState


# --- Factory Functions for Testing ---


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
        receptiveness=Receptiveness(music=0.7, journaling=0.6),
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
        receptiveness=Receptiveness(music=0.8, breathing=0.9, challenge=0.2),
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
