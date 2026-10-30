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

from app.db import get_db
from app.middleware.auth import require_user
from app.routers.memory_schemas import (
    DeleteEntryRequest,
    EmotionalPatternsUpdate,
    MemoryNoteCreate,
    MemoryNoteUpdate,
    PeopleUpdate,
    PreferencesUpdate,
)
from app.routers.memory_service import delete_memory_entry
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


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


@router.patch("/emotional_patterns", summary="Update emotional patterns (system-managed; any authenticated user may override their own)")
async def update_emotional_patterns(
    req: EmotionalPatternsUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_user),
):
    """
    Update emotional patterns. Usually system-managed, but user can override.

    Dotted paths, not {"emotional_patterns": updates} — the same whole-
    subdocument bug fixed in update_preferences below. This endpoint is called
    piecemeal (services/memory_extraction.py records trigger_topics and
    effective_coping on separate turns), so a caller sending only
    most_common_emotion would otherwise wipe whatever the other calls had
    just added.
    """
    user_id = str(current_user["_id"])
    now = datetime.datetime.now(datetime.UTC)

    updates = req.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No pattern fields provided")

    changes: dict[str, Any] = {f"emotional_patterns.{key}": value for key, value in updates.items()}
    changes["updated_at"] = now

    await db.user_memory.update_one({"user_id": user_id}, {"$set": changes})
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
    return await delete_memory_entry(user_id=user_id, req=req, db=db)
