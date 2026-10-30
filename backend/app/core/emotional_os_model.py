"""Pydantic model for the persisted emotional operating state."""

from __future__ import annotations

import typing
from datetime import datetime

from pydantic import BaseModel, Field

from app.core.emotional_os_types import AgeGroup, Modality, PeopleGraph, Receptiveness


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
    distortion_score: float = Field(
        default=0.0,
        ge=0,
        le=1,
        description=(
            "The classifier's actual score for distortion_label. Carried so "
            "downstream agents report the real number instead of inventing "
            "one -- distortion_agent used to hardcode 0.5 whenever a label "
            "existed at all."
        ),
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

    introvert_score: float = Field(
        default=0.5,
        ge=0,
        le=1,
        description=(
            "Standing social-disposition profile: 0.0 introvert, 1.0 extrovert. "
            "Inferred by PersonalityAgent over many turns and persisted at "
            "preferences.introvert_score â€” distinct from social_energy, which "
            "is how much social capacity is available *right now*."
        ),
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
        description="User-set Gentle<->Direct preference (Settings > General)",
    )

    personality: str | None = Field(
        default=None,
        description="How the user describes themselves (Settings > General)",
    )

    custom_instructions: str | None = Field(
        default=None,
        description="Free-text 'instructions for Mindlens' (Settings > General)",
    )

    checkin_preferred_time: typing.Literal["morning", "evening", "whenever"] | None = Field(
        default=None,
        description="Onboarding step 3 â€” when CheckInScheduler should land a proactive check-in",
    )

    memory_depth: typing.Literal["everything", "key_details", "nothing"] = Field(
        default="everything",
        description=(
            "Your Mindlens > Memory depth control. 'nothing' also stops "
            "services/memory_extraction.py from recording new facts, not just "
            "recall — a user who asked MindLens not to draw on memory "
            "shouldn't have new memory quietly building up behind the "
            "scenes either."
        ),
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
        }
        return routing

    def to_dict(self) -> dict:
        # mode="json" so PeopleGraph.mentioned_at, last_crisis_mention and
        # calculated_at come out as ISO strings, not native datetime objects.
        # This dict routinely ends up in a WebSocket send_json() call
        # (streaming.py -> connection_manager), which uses the stdlib json
        # module and has no datetime support -- a plain .model_dump() here
        # crashed that send outright the moment any of those fields was
        # populated (e.g. the first turn after a person exists in memory),
        # silently dropping the reply with no error reaching the user.
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: dict) -> EmotionalOperatingState:
        return cls(**data)


# --- Backward Compatibility Alias ---
EmotionalOS = EmotionalOperatingState


# --- Factory Functions for Testing ---

