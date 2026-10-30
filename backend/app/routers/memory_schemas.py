"""Validation models for memory API requests."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MemoryNoteCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)

class MemoryNoteUpdate(BaseModel):
    note_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1, max_length=1000)

class PeopleUpdate(BaseModel):
    people: dict[str, dict[str, str]] = Field(..., description="Name -> {role, context, sentiment}")

class PreferencesUpdate(BaseModel):
    mindfulness_style: str | None = Field(None, max_length=100)
    introvert_score: float | None = Field(None, ge=0.0, le=1.0)
    preferred_modality: str | None = Field(None, max_length=50)
    checkin_preferred_time: str | None = Field(None, pattern="^(morning|evening|whenever)$")
    # Your Mindlens studio. memory_recall.py already reads both of these back
    # into the EOS each turn (modality override, recall depth) — this is what
    # lets the user actually set them.
    tone_preference: str | None = Field(None, pattern="^(gentle|balanced|direct)$")
    memory_depth: str | None = Field(None, pattern="^(everything|key_details|nothing)$")
    companion_name: str | None = Field(None, min_length=1, max_length=40)
    # Which of the five locked companions (frontend lib/companions.ts)
    # renders as the user's default companion.
    companion_id: str | None = Field(None, pattern="^(ember|lens|flit|tide|fern)$")
    # --- Settings > General -------------------------------------------------
    # How the user describes themselves. Feeds the empathy agent's system
    # prompt, so it changes how replies are written — not a cosmetic label.
    personality: str | None = Field(
        None,
        pattern="^(overthinker|doer|highly_sensitive|analytical|optimist|realist|"
        "anxious_achiever|quiet_observer|people_person|private)$",
    )
    # Free-text "instructions for Mindlens", same idea as Claude's custom
    # instructions. Capped and treated as untrusted input downstream.
    custom_instructions: str | None = Field(None, max_length=1500)
    # "auto" = the room recolours from each turn's detected emotion (default).
    # "manual" = the user pins one palette and it never shifts.
    palette_mode: str | None = Field(None, pattern="^(auto|manual)$")
    manual_palette: str | None = Field(
        None,
        pattern="^(calm|hopeful|joyful|tender|balanced|anxious|low|grief|angry|"
        "envious|ashamed|flat)$",
    )
    # design.md §2: "user can cap it in Your Mindlens" — caps field opacity,
    # glow radius, companion motion amplitude and accent saturation together.
    # 1.0 = uncapped (the emotion's own read decides); lower values flatten
    # the room for anyone who wants stillness over intensity.
    intensity_cap: float | None = Field(None, ge=0.1, le=1.0)


class EmotionalPatternsUpdate(BaseModel):
    most_common_emotion: str | None = None
    average_distress: float | None = Field(None, ge=0.0, le=1.0)
    trigger_topics: list[str] | None = None
    effective_coping: list[str] | None = None

class DeleteEntryRequest(BaseModel):
    section: str = Field(..., pattern="^(people|trigger_topics|effective_coping|milestones|raw_notes)$")
    key: str = Field(..., description="Key or note_id to delete")


