"""
MindLens Memory Router
======================
CRUD for the user_memory document (the 'memory.md' in the UI).

Features:
  - Read full memory
  - Update profile, people, preferences, emotional_patterns
  - Add/delete raw_notes (user-editable free-text notes)
  - Delete specific entries (people, trigger_topics, etc.)
  - Transparency: user sees exactly what MindLens remembers

All endpoints enforce user_id isolation.
"""

from __future__ import annotations

import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.db import get_db
from app.middleware.auth import require_user
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


# --- Pydantic Schemas ---

class MemoryNoteCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)

class MemoryNoteUpdate(BaseModel):
    note_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1, max_length=1000)

class PeopleUpdate(BaseModel):
    people: dict[str, dict[str, str]] = Field(..., description="Name -> {role, context, sentiment}")

class PreferencesUpdate(BaseModel):
    music_genres: list[str] | None = None
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


# --- Routes ---

@router.get("", summary="Get full user memory")
async def get_memory(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_user),
):
    """
    Return the full user_memory document.

    This is the 'memory card' shown in the right panel.
    """
    user_id = str(current_user["_id"])
    memory = await db.user_memory.find_one({"user_id": user_id})
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found. Complete onboarding first.")
    memory["id"] = str(memory.pop("_id", ""))
    return memory


@router.patch("/profile", summary="Update memory profile")
async def update_profile(
    updates: dict[str, Any],
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_user),
):
    """Update the profile section of user_memory."""
    user_id = str(current_user["_id"])
    now = datetime.datetime.now(datetime.UTC)

    # Only allow specific fields
    allowed = {"name", "nickname", "age", "age_group"}
    filtered = {k: v for k, v in updates.items() if k in allowed}

    if not filtered:
        raise HTTPException(status_code=400, detail="No valid profile fields provided")

    await db.user_memory.update_one(
        {"user_id": user_id},
        {"$set": {"profile": filtered, "updated_at": now}},
    )
    return {"message": "Profile updated"}


@router.patch("/people", summary="Update people graph")
async def update_people(
    req: PeopleUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_user),
):
    """Replace or update the people graph."""
    user_id = str(current_user["_id"])
    now = datetime.datetime.now(datetime.UTC)

    await db.user_memory.update_one(
        {"user_id": user_id},
        {"$set": {"people": req.people, "updated_at": now}},
    )
    return {"message": "People graph updated", "count": len(req.people)}


@router.patch("/preferences", summary="Update preferences")
async def update_preferences(
    req: PreferencesUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_user),
):
    """Update the preferences section."""
    user_id = str(current_user["_id"])
    now = datetime.datetime.now(datetime.UTC)

    updates = req.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No preference fields provided")

    # Dotted paths, not {"preferences": updates} — a whole-subdocument $set
    # replaces every preference the caller didn't send. That was survivable
    # while one page saved all fields at once, but settings is split into
    # independent sections, so saving Appearance would have wiped the
    # companion, tone and memory-depth the user had chosen elsewhere.
    changes: dict[str, Any] = {f"preferences.{key}": value for key, value in updates.items()}
    changes["updated_at"] = now

    await db.user_memory.update_one({"user_id": user_id}, {"$set": changes})
    return {"message": "Preferences updated"}


@router.patch("/emotional_patterns", summary="Update emotional patterns (system-managed, admin only)")
async def update_emotional_patterns(
    req: EmotionalPatternsUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_user),
):
    """
    Update emotional patterns. Usually system-managed, but user can override.
    """
    user_id = str(current_user["_id"])
    now = datetime.datetime.now(datetime.UTC)

    updates = req.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No pattern fields provided")

    await db.user_memory.update_one(
        {"user_id": user_id},
        {"$set": {"emotional_patterns": updates, "updated_at": now}},
    )
    return {"message": "Emotional patterns updated"}


@router.post("/notes", summary="Add a raw note")
async def add_note(
    req: MemoryNoteCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_user),
):
    """Add a user-editable free-text note to memory."""
    user_id = str(current_user["_id"])
    now = datetime.datetime.now(datetime.UTC)
    import uuid
    note_id = str(uuid.uuid4())

    note_doc = {
        "note_id": note_id,
        "text": req.text,
        "created_at": now,
        "updated_at": now,
    }

    await db.user_memory.update_one(
        {"user_id": user_id},
        {
            "$push": {"raw_notes": note_doc},
            "$set": {"updated_at": now},
        },
    )
    return {"message": "Note added", "note_id": note_id}


@router.put("/notes/{note_id}", summary="Update a raw note")
async def update_note(
    note_id: str,
    req: MemoryNoteUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_user),
):
    """Update a specific note by note_id."""
    user_id = str(current_user["_id"])
    now = datetime.datetime.now(datetime.UTC)

    result = await db.user_memory.update_one(
        {"user_id": user_id, "raw_notes.note_id": note_id},
        {
            "$set": {
                "raw_notes.$.text": req.text,
                "raw_notes.$.updated_at": now,
                "updated_at": now,
            }
        },
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Note not found")

    return {"message": "Note updated"}


@router.delete("/notes/{note_id}", summary="Delete a raw note")
async def delete_note(
    note_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_user),
):
    """Delete a specific note by note_id."""
    user_id = str(current_user["_id"])
    now = datetime.datetime.now(datetime.UTC)

    await db.user_memory.update_one(
        {"user_id": user_id},
        {
            "$pull": {"raw_notes": {"note_id": note_id}},
            "$set": {"updated_at": now},
        },
    )
    return {"message": "Note deleted"}


@router.post("/delete_entry", summary="Delete a specific memory entry")
async def delete_entry(
    req: DeleteEntryRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_user),
):
    """
    Delete a specific entry from a memory section.

    - people: key is the person's name
    - trigger_topics: key is the topic string
    - effective_coping: key is the strategy string
    - milestones: key is the milestone string
    - raw_notes: key is the note_id
    """
    user_id = str(current_user["_id"])
    now = datetime.datetime.now(datetime.UTC)

    if req.section == "people":
        await db.user_memory.update_one(
            {"user_id": user_id},
            {
                "$unset": {f"people.{req.key}": ""},
                "$set": {"updated_at": now},
            },
        )
    elif req.section in ("trigger_topics", "effective_coping", "milestones"):
        # `milestones` lives at the document root; the other two are nested
        # under `emotional_patterns`. The previous ternary returned a whole
        # `{"$pull": ...}` document for the milestones branch while already
        # inside a "$pull" key, producing `{"$pull": {"$pull": {...}}}` —
        # every milestone delete errored. Only the *path* differs, so branch
        # on the path alone.
        field = (
            "milestones"
            if req.section == "milestones"
            else f"emotional_patterns.{req.section}"
        )
        await db.user_memory.update_one(
            {"user_id": user_id},
            {
                "$pull": {field: req.key},
                "$set": {"updated_at": now},
            },
        )
    elif req.section == "raw_notes":
        await db.user_memory.update_one(
            {"user_id": user_id},
            {
                "$pull": {"raw_notes": {"note_id": req.key}},
                "$set": {"updated_at": now},
            },
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid section")

    return {"message": f"Deleted from {req.section}"}
