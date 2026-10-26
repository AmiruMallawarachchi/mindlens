"""EOS enums and nested value objects."""

import enum
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

