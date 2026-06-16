"""Emotional Operating System (EOS) — typed state snapshot per turn."""

from __future__ import annotations

from typing import Optional, Literal
from pydantic import BaseModel, Field


class InterventionReceptiveness(BaseModel):
    """What interventions will land right now."""

    music: float = Field(default=0.5, ge=0.0, le=1.0)
    journaling: float = Field(default=0.5, ge=0.0, le=1.0)
    challenge: float = Field(default=0.0, ge=0.0, le=1.0)
    grounding: float = Field(default=0.5, ge=0.0, le=1.0)
    breathing: float = Field(default=0.5, ge=0.0, le=1.0)
    routine: float = Field(default=0.5, ge=0.0, le=1.0)
    social_support: float = Field(default=0.5, ge=0.0, le=1.0)


class EmotionalOperatingState(BaseModel):
    """
    The core object of MindLens. Built fresh every turn.
    Every agent reads this instead of raw text.
    """

    # Surface vs depth
    surface_emotion: str = Field(default="neutral")
    core_emotion: str = Field(default="neutral")
    suppressed_emotion: Optional[str] = Field(default=None)

    # Continuous scores
    emotional_stability: float = Field(default=0.5, ge=0.0, le=1.0)
    mental_fatigue: float = Field(default=0.5, ge=0.0, le=1.0)
    social_energy: float = Field(default=0.5, ge=0.0, le=1.0)
    distress_level: float = Field(default=0.5, ge=0.0, le=1.0)
    trust_level: float = Field(default=0.3, ge=0.0, le=1.0)

    # Relationship
    attachment_style: Literal["secure", "anxious", "avoidant", "unknown"] = Field(default="unknown")

    # Receptiveness
    receptiveness: InterventionReceptiveness = Field(default_factory=InterventionReceptiveness)

    # Basic
    valence: Literal["positive", "negative", "neutral"] = Field(default="neutral")

    # Routing (set by Orchestrator)
    modality: Literal["CBT", "DBT", "ACT", "Mindfulness", "MI"] = Field(default="CBT")
    run_distortion: bool = Field(default=False)
    run_challenge: bool = Field(default=False)
    run_music: bool = Field(default=False)
    run_routine: bool = Field(default=False)
    run_journaling: bool = Field(default=False)
    run_mindfulness: bool = Field(default=False)

    # Session context
    session_depth: float = Field(default=0.0, ge=0.0, le=1.0)
    alliance_score: float = Field(default=0.0, ge=0.0, le=1.0)

    def to_dict(self) -> dict:
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict) -> "EmotionalOperatingState":
        return cls(**data)