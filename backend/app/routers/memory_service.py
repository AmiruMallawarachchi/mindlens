"""Storage operations for user memory entries."""

from __future__ import annotations

import datetime

from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.routers.memory_schemas import DeleteEntryRequest


async def delete_memory_entry(
    user_id: str, req: DeleteEntryRequest, db: AsyncIOMotorDatabase
) -> dict[str, str]:
    """Delete one entry from its supported memory section."""
    now = datetime.datetime.now(datetime.UTC)
    if req.section == "people":
        await db.user_memory.update_one(
            {"user_id": user_id},
            {"$unset": {f"people.{req.key}": ""}, "$set": {"updated_at": now}},
        )
    elif req.section in ("trigger_topics", "effective_coping", "milestones"):
        field = (
            "milestones"
            if req.section == "milestones"
            else f"emotional_patterns.{req.section}"
        )
        await db.user_memory.update_one(
            {"user_id": user_id},
            {"$pull": {field: req.key}, "$set": {"updated_at": now}},
        )
    elif req.section == "raw_notes":
        await db.user_memory.update_one(
            {"user_id": user_id},
            {"$pull": {"raw_notes": {"note_id": req.key}}, "$set": {"updated_at": now}},
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid section")
    return {"message": f"Deleted from {req.section}"}
