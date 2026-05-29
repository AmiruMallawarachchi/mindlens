from pydantic import BaseModel, Field
from typing import Optional, Literal

class InterventionReceptiveness(BaseModel):
    """What interventions will land right now"""
    music: float = Field(0.5, ge=0.0, le=1.0)
    journaling: float = Field(0.5, ge=0.0, le=1.0)
    challenge: float = Field(0.0, ge=0.0, le=1.0)
    grounding: float = Field(0.5, ge=0.0, le=1.0)
    breathing: float = Field(0.5, ge=0.0, le=1.0)
    routine: float = Field(0.5, ge=0.0, le=1.0)
    social_support: float = Field(0.5, ge=0.0, le=1.0)

class EmotionalOperatingState(BaseModel):
    """
    The core object of MindLens. Built fresh every turn.
    Every agent reads this instead of raw text.
    """
    # Surface vs depth
    surface_emotion: str = "neutral"
    core_emotion: str = "neutral"
    suppressed_emotion: Optional[str] = None
    
    # Continuous scores
    emotional_stability: float = Field(0.5, ge=0.0, le=1.0)
    mental_fatigue: float = Field(0.5, ge=0.0, le=1.0)
    social_energy: float = Field(0.5, ge=0.0, le=1.0)
    distress_level: float = Field(0.5, ge=0.0, le=1.0)
    trust_level: float = Field(0.3, ge=0.0, le=1.0)
    
    # Relationship
    attachment_style: Literal["secure", "anxious", "avoidant", "unknown"] = "unknown"
    
    # Receptiveness
    receptiveness: InterventionReceptiveness = InterventionReceptiveness() # type: ignore
    
    # Basic
    valence: Literal["positive", "negative", "neutral"] = "neutral"
    
    # Routing (set by Orchestrator)
    modality: Literal["CBT", "DBT", "ACT", "Mindfulness", "MI"] = "CBT"
    run_distortion: bool = False
    run_challenge: bool = False
    run_music: bool = False
    run_routine: bool = False
    run_journaling: bool = False
    run_mindfulness: bool = False
    
    # Session context
    session_depth: float = Field(0.0, ge=0.0, le=1.0)
    alliance_score: float = Field(0.0, ge=0.0, le=1.0)
    
    def to_dict(self) -> dict:
        return self.model_dump()
    
    @classmethod
    def from_dict(cls, data: dict) -> "EmotionalOperatingState":
        return cls(**data)