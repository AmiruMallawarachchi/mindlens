"""Current-user profile routes for the authentication API."""

from __future__ import annotations

import datetime
from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import settings
from app.db import document_id_filter, get_db
from app.middleware.auth import require_user
from app.routers.auth_schemas import ProfileUpdate, UserResponse

router = APIRouter()
@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
)
async def get_me(
    current_user: dict = Depends(require_user),
):
    """
    Return the current authenticated user's profile.

    Requires valid JWT in Authorization header.
    """
    return UserResponse(
        id=str(current_user["_id"]),
        email=current_user["email"],
        name=current_user["name"],
        nickname=current_user.get("nickname"),
        age=current_user["age"],
        age_group=current_user.get("age_group", "adult"),
        role=current_user.get("role", settings.USER_ROLE_NAME),
        onboarding_complete=current_user.get("onboarding_complete", False),
        created_at=current_user["created_at"],
    )


@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Update the current user's profile",
)
async def update_me(
    req: ProfileUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_user),
):
    """Update the signed-in user's own profile fields."""
    updates = req.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No profile fields provided")

    if "nickname" in updates and updates["nickname"]:
        updates["nickname"] = updates["nickname"].strip()

    await db.users.update_one(
        document_id_filter(str(current_user["_id"])),
        {"$set": {**updates, "updated_at": datetime.datetime.now(datetime.UTC)}},
    )

    # Keep the memory doc's mirrored profile in step ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â memory_recall.py reads
    # the nickname from there when personalising a turn, so letting the two
    # drift would mean the companion greets you by the old name.
    if "nickname" in updates:
        await db.user_memory.update_one(
            {"user_id": str(current_user["_id"])},
            {"$set": {"profile.nickname": updates["nickname"]}},
        )

    merged = {**current_user, **updates}
    return UserResponse(
        id=str(merged["_id"]),
        email=merged["email"],
        name=merged["name"],
        nickname=merged.get("nickname"),
        age=merged["age"],
        age_group=merged.get("age_group", "adult"),
        role=merged.get("role", settings.USER_ROLE_NAME),
        onboarding_complete=merged.get("onboarding_complete", False),
        created_at=merged["created_at"],
    )

