"""
MindLens Journal Router
========================
CRUD for user journal entries — design.md §4.2's Journal board:
prompt hero ("A prompt for today" + Start writing), recent-entries 3-card
grid (date, title, excerpt), New entry button.

Previously the Journal tab had no backend at all — journaling_agent
(SYSTEM.md §5.10) generates reflective questions *inline during chat*, but
there was no way to write, store, or revisit a standalone journal entry.

The daily prompt is a curated rotation rather than an LLM call: it's cheap,
always available, and — unlike a generated prompt — never varies in quality
turn to turn. It rotates by calendar date so everyone sees the same prompt
on a given day, plus a per-user offset so it doesn't always land on the same
prompt for a given weekday.

All endpoints enforce user_id isolation — users can only see their own
entries.
"""

from __future__ import annotations

import datetime
import uuid
import zlib
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.db import get_db
from app.middleware.auth import require_user
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()

EXCERPT_LENGTH = 160

# Curated, CBT-informed reflective prompts (SYSTEM.md §7 voice rules: warm,
# concrete, never diagnostic). Rotated by date, not generated, so the prompt
# is instant and free rather than an LLM call on every page view.
DAILY_PROMPTS: list[str] = [
    "What's one thing that happened today that you haven't fully let yourself feel yet?",
    "If a friend told you what you're telling yourself right now, what would you say back to them?",
    "What's a small moment from this week you'd like to remember?",
    "What are you carrying right now that isn't actually yours to carry?",
    "What did you need today that you didn't get — and who could you ask for it?",
    "What's a thought that's been on repeat lately? Where do you think it came from?",
    "What's something you did today that your future self might thank you for?",
    "Who or what made today a little easier, even in a small way?",
    "What's a fear you're avoiding looking at directly?",
    "If today had a title, what would it be — and why?",
    "What's one thing you're proud of that you haven't said out loud?",
    "What would 'enough' look like today, if you let it be smaller than usual?",
    "What's a pattern you've noticed in how you react to stress?",
    "What's something you wish someone had asked you today?",
    "What's a boundary you held (or wish you'd held) recently?",
    "What's weighing on you that would feel lighter just by writing it down?",
    "What's something kind you could say to yourself right now?",
    "What went differently than you expected today, for better or worse?",
    "What's a worry that, if you're honest, is really about something else?",
    "What's one thing you're looking forward to, even a little?",
]


# --- Pydantic Schemas -------------------------------------------------------


class JournalEntryCreate(BaseModel):
    title: str | None = Field(None, max_length=200)
    text: str = Field(..., min_length=1, max_length=8000)
    prompt_used: str | None = Field(None, max_length=500)


class JournalEntryUpdate(BaseModel):
    title: str | None = Field(None, max_length=200)
    text: str = Field(..., min_length=1, max_length=8000)


class JournalEntryResponse(BaseModel):
    entry_id: str
    title: str | None
    text: str
    prompt_used: str | None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class JournalEntrySummary(BaseModel):
    entry_id: str
    title: str | None
    excerpt: str
    created_at: datetime.datetime


class JournalPromptResponse(BaseModel):
    prompt: str
    date: str


# --- Helpers -----------------------------------------------------------------


def _excerpt(text: str, length: int = EXCERPT_LENGTH) -> str:
    stripped = " ".join(text.split())
    if len(stripped) <= length:
        return stripped
    return stripped[:length].rsplit(" ", 1)[0] + "…"


def _entry_response(doc: dict[str, Any]) -> JournalEntryResponse:
    return JournalEntryResponse(
        entry_id=doc["entry_id"],
        title=doc.get("title"),
        text=doc["text"],
        prompt_used=doc.get("prompt_used"),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


# --- Routes ------------------------------------------------------------------


@router.get("/prompt", response_model=JournalPromptResponse, summary="Get today's journaling prompt")
async def get_daily_prompt(
    current_user: dict = Depends(require_user),
) -> JournalPromptResponse:
    """A stable prompt for today, varied per user so everyone doesn't see
    the same one, and varied by date so a given user doesn't see the same
    one every day."""
    today = datetime.datetime.now(datetime.UTC).date()
    user_id = str(current_user["_id"])
    # zlib.crc32 rather than the builtin hash(): str hashing is randomised
    # per-process (PYTHONHASHSEED), which would change a user's "today"
    # prompt on every server restart.
    offset = zlib.crc32(user_id.encode("utf-8"))
    index = (today.toordinal() + offset) % len(DAILY_PROMPTS)
    return JournalPromptResponse(prompt=DAILY_PROMPTS[index], date=today.isoformat())


@router.post(
    "",
    response_model=JournalEntryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a journal entry",
)
async def create_entry(
    req: JournalEntryCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_user),
) -> JournalEntryResponse:
    user_id = str(current_user["_id"])
    now = datetime.datetime.now(datetime.UTC)
    entry_id = str(uuid.uuid4())

    doc = {
        "entry_id": entry_id,
        "user_id": user_id,
        "title": req.title,
        "text": req.text,
        "prompt_used": req.prompt_used,
        "created_at": now,
        "updated_at": now,
    }
    await db.journal_entries.insert_one(doc)
    logger.info("Journal entry created: %s for user %s", entry_id, user_id)
    return _entry_response(doc)


@router.get(
    "",
    response_model=list[JournalEntrySummary],
    summary="List journal entries",
)
async def list_entries(
    limit: int = Query(default=30, ge=1, le=100),
    skip: int = Query(default=0, ge=0),
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_user),
) -> list[JournalEntrySummary]:
    user_id = str(current_user["_id"])
    cursor = (
        db.journal_entries.find({"user_id": user_id})
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    entries = []
    async for doc in cursor:
        entries.append(
            JournalEntrySummary(
                entry_id=doc["entry_id"],
                title=doc.get("title"),
                excerpt=_excerpt(doc["text"]),
                created_at=doc["created_at"],
            )
        )
    return entries


@router.get(
    "/{entry_id}",
    response_model=JournalEntryResponse,
    summary="Get a single journal entry",
)
async def get_entry(
    entry_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_user),
) -> JournalEntryResponse:
    user_id = str(current_user["_id"])
    doc = await db.journal_entries.find_one({"entry_id": entry_id, "user_id": user_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found")
    return _entry_response(doc)


@router.put(
    "/{entry_id}",
    response_model=JournalEntryResponse,
    summary="Update a journal entry",
)
async def update_entry(
    entry_id: str,
    req: JournalEntryUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_user),
) -> JournalEntryResponse:
    user_id = str(current_user["_id"])
    now = datetime.datetime.now(datetime.UTC)

    doc = await db.journal_entries.find_one({"entry_id": entry_id, "user_id": user_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found")

    updates = {"text": req.text, "title": req.title, "updated_at": now}
    await db.journal_entries.update_one(
        {"entry_id": entry_id, "user_id": user_id},
        {"$set": updates},
    )
    doc.update(updates)
    return _entry_response(doc)


@router.delete(
    "/{entry_id}",
    summary="Delete a journal entry",
)
async def delete_entry(
    entry_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_user),
) -> dict[str, str]:
    user_id = str(current_user["_id"])
    result = await db.journal_entries.delete_one({"entry_id": entry_id, "user_id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found")
    return {"message": "Journal entry deleted"}
