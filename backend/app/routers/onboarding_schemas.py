"""Validation and response schemas for onboarding routes."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class OnboardingStep1(BaseModel):
    """Step 1: Name"""
    name: str = Field(..., min_length=1, max_length=100)

class OnboardingStep2(BaseModel):
    """Step 2: Nickname"""
    nickname: str | None = Field(None, max_length=100)

class OnboardingStep3(BaseModel):
    """Step 3: Age"""
    age: int = Field(..., ge=13, le=100)

class OnboardingStep4(BaseModel):
    """Step 4: People (optional, up to 2)"""
    # min_length=0: naming someone is optional. Requiring it made the whole
    # onboarding un-skippable, and a user with nobody they want to name (or
    # who simply doesn't want to yet) could not get past the step. People can
    # be added any time from Memory instead.
    people: list[dict[str, str]] = Field(..., min_length=0, max_length=2)
    # Each: {"name": "Ravi", "role": "best friend", "context": "also doing same exam"}

class OnboardingStep5(BaseModel):
    """Step 5: Check-in preference"""
    checkin_preferred_time: str = Field(..., pattern="^(morning|evening|whenever)$")

class OnboardingCompleteRequest(BaseModel):
    """Complete all steps at once (alternative to step-by-step)"""
    name: str = Field(..., min_length=1, max_length=100)
    nickname: str | None = Field(None, max_length=100)
    age: int = Field(..., ge=13, le=100)
    # Optional — see OnboardingStep4 for why.
    people: list[dict[str, str]] = Field(..., min_length=0, max_length=2)
    checkin_preferred_time: str = Field(..., pattern="^(morning|evening|whenever)$")
    # Both optional and both already fully wired (memory.py's PreferencesUpdate,
    # memory_recall.py, empathy_agent.py) — surfaced here so the very first
    # reply is personalized, not just replies after a trip to Settings.
    personality: str | None = Field(
        None,
        pattern="^(overthinker|doer|highly_sensitive|analytical|optimist|realist|"
        "anxious_achiever|quiet_observer|people_person|private)$",
    )
    tone_preference: str | None = Field(None, pattern="^(gentle|balanced|direct)$")

class OnboardingStatusResponse(BaseModel):
    """Current onboarding status"""
    user_id: str
    onboarding_complete: bool
    current_step: int
    profile: dict[str, Any]

class OnboardingCompleteResponse(BaseModel):
    """Response after completing onboarding"""
    user_id: str
    onboarding_complete: bool
    session_id: str | None
    access_token: str | None
    token_type: str = "bearer"
    expires_in: int


