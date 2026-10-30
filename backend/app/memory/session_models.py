"""Pydantic records used by session memory."""

from __future__ import annotations

import datetime

import pydantic


class Turn(pydantic.BaseModel):
    """Single conversational turn."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime.datetime
    emotion: str | None = None  # user emotion (if detected)
    distress: float | None = None  # user distress level (0-1)


class SessionSnapshot(pydantic.BaseModel):
    """EOS state at a specific point in session."""

    turn_number: int
    timestamp: datetime.datetime
    surface_emotion: str
    core_emotion: str
    distress_level: float
    trust_level: float
    alliance_score: float
    modality: str  # "CBT", "Mindfulness", etc.


