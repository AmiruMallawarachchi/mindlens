# backend/app/core/emotional_os.py
"""Emotional Operating System (EOS) — typed state snapshot per turn."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EmotionalOS(BaseModel):
    """
    Immutable snapshot of the user's psychological state at a single turn.
    Passed through the entire agent pipeline.
    """

    surface_emotion: str = Field(
        ..., description="Highest-scoring emotion from 28-class output"
    )
    core_emotion: str = Field(
        ..., description="Highest-scoring NEGATIVE emotion"
    )
    suppressed_emotion: str = Field(
        ..., description="Second-highest emotion (often masked)"
    )
    distress_level: float = Field(
        ..., ge=0.0, le=1.0, description="Composite 0-1 distress score"
    )
    crisis_flag: bool = Field(
        False, description="True if safety gate triggered"
    )
    crisis_score: float = Field(
        0.0, ge=0.0, le=1.0, description="Raw crisis classifier probability"
    )
    mh_scores: dict[str, float] = Field(
        default_factory=dict, description="Mental health condition scores"
    )
    emotion_scores: dict[str, float] = Field(
        default_factory=dict, description="All 28 emotion class scores"
    )
    modality: str = Field(
        "CBT", description="Selected therapy modality"
    )
    trust_level: float = Field(
        0.5, ge=0.0, le=1.0, description="Therapeutic alliance estimate"
    )
    session_depth: float = Field(
        0.0, ge=0.0, le=1.0, description="How deep the current session has gone"
    )
    receptiveness: dict[str, float] = Field(
        default_factory=dict, description="Per-intervention effectiveness scores"
    )