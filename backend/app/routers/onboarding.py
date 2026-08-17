"""
MindLens Onboarding Router
===========================
5-step wizard API for new user onboarding.

Steps:
  1. Name
  2. Nickname (or skip)
  3. Age (determines age_group: teen/adult)
  4. People graph (up to 2 important people)
  5. Check-in preference (morning/evening/whenever)

Creates:
  - user document in users collection (if not already registered)
  - user_memory document with profile, people, preferences

After onboarding, the first session is automatically created.
"""

from __future__ import annotations

import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.config import settings
from app.db import document_id_filter, get_db
from app.middleware.auth import create_token_pair, require_user
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


# --- Pydantic Schemas ---

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
    """Step 4: People (up to 2)"""
    people: list[dict[str, str]] = Field(..., min_length=1, max_length=2)
    # Each: {"name": "Ravi", "role": "best friend", "context": "also doing same exam"}

class OnboardingStep5(BaseModel):
    """Step 5: Check-in preference"""
    checkin_preferred_time: str = Field(..., pattern="^(morning|evening|whenever)$")

class OnboardingCompleteRequest(BaseModel):
    """Complete all steps at once (alternative to step-by-step)"""
    name: str = Field(..., min_length=1, max_length=100)
    nickname: str | None = Field(None, max_length=100)
    age: int = Field(..., ge=13, le=100)
    people: list[dict[str, str]] = Field(..., min_length=1, max_length=2)
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


# --- Helpers ---

def _age_group(age: int) -> str:
    return "teen" if age <= 19 else "adult"

def _build_people_graph(people: list[dict[str, str]]) -> dict[str, Any]:
    graph = {}
    for p in people:
        name = p.get("name", "").strip()
        if not name:
            continue
        graph[name] = {
            "role": p.get("role", ""),
            "context": p.get("context", ""),
            "sentiment": "positive",
        }
    return graph


# --- Routes ---

@router.get("/status", response_model=OnboardingStatusResponse, summary="Get onboarding status")
async def get_onboarding_status(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_user),
):
    """Check the user's current onboarding progress."""
    user_id = str(current_user["_id"])
    user = await db.users.find_one(document_id_filter(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Determine current step
    step = 1
    if user.get("name"):
        step = 2
    if user.get("nickname") is not None or user.get("name"):
        step = 3
    if user.get("age"):
        step = 4
    if user.get("onboarding_people"):
        step = 5
    if user.get("onboarding_complete"):
        step = 6

    return OnboardingStatusResponse(
        user_id=user_id,
        onboarding_complete=user.get("onboarding_complete", False),
        current_step=step,
        profile={
            "name": user.get("name"),
            "nickname": user.get("nickname"),
            "age": user.get("age"),
            "age_group": user.get("age_group"),
            "people": user.get("onboarding_people", []),
            "checkin_preferred_time": user.get("checkin_preferred_time"),
        },
    )


@router.post("/step/{step_number}", response_model=dict, summary="Submit onboarding step")
async def submit_onboarding_step(
    step_number: int,
    data: dict[str, Any],
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_user),
):
    """
    Submit one step of the onboarding wizard.

    Steps:
      1 → name
      2 → nickname
      3 → age (also sets age_group)
      4 → people (list of {name, role, context})
      5 → checkin_preferred_time
    """
    user_id = str(current_user["_id"])
    now = datetime.datetime.now(datetime.UTC)

    if step_number == 1:
        req = OnboardingStep1(**data)
        await db.users.update_one(
            document_id_filter(user_id),
            {"$set": {"name": req.name, "updated_at": now}},
        )
        return {"step": 1, "status": "ok", "next_step": 2}

    elif step_number == 2:
        req = OnboardingStep2(**data)
        nickname = req.nickname or (
            await db.users.find_one(document_id_filter(user_id), {"name": 1})
        ).get("name", "friend")
        await db.users.update_one(
            document_id_filter(user_id),
            {"$set": {"nickname": nickname, "updated_at": now}},
        )
        return {"step": 2, "status": "ok", "next_step": 3}

    elif step_number == 3:
        req = OnboardingStep3(**data)
        age_group = _age_group(req.age)
        await db.users.update_one(
            document_id_filter(user_id),
            {"$set": {"age": req.age, "age_group": age_group, "updated_at": now}},
        )
        return {"step": 3, "status": "ok", "next_step": 4}

    elif step_number == 4:
        req = OnboardingStep4(**data)
        await db.users.update_one(
            document_id_filter(user_id),
            {"$set": {"onboarding_people": req.people, "updated_at": now}},
        )
        return {"step": 4, "status": "ok", "next_step": 5}

    elif step_number == 5:
        req = OnboardingStep5(**data)
        await db.users.update_one(
            document_id_filter(user_id),
            {
                "$set": {
                    "checkin_preferred_time": req.checkin_preferred_time,
                    "onboarding_complete": True,
                    "updated_at": now,
                }
            },
        )

        # Create user_memory document
        user = await db.users.find_one(document_id_filter(user_id))
        people_graph = _build_people_graph(user.get("onboarding_people", []))
        await db.user_memory.update_one(
            {"user_id": user_id},
            {
                "$setOnInsert": {
                    "user_id": user_id,
                    "display_name": f"{user.get('nickname', user.get('name', 'friend'))}'s Memory",
                    "created_at": now,
                },
                "$set": {
                    "profile": {
                        "name": user.get("name"),
                        "nickname": user.get("nickname"),
                        "age": user.get("age"),
                        "age_group": user.get("age_group"),
                        "onboarding_complete": True,
                    },
                    "people": people_graph,
                    "preferences": {
                        "checkin_preferred_time": req.checkin_preferred_time,
                        "music_genres": [],
                        "mindfulness_style": "",
                        # No introvert_score here — see the matching comment
                        # on the /complete path below for why.
                        "preferred_modality": "CBT",
                    },
                    "emotional_patterns": {
                        "most_common_emotion": None,
                        "average_distress": 0.0,
                        "trigger_topics": [],
                        "effective_coping": [],
                    },
                    "milestones": ["Completed onboarding"],
                    "raw_notes": [],
                    "updated_at": now,
                },
            },
            upsert=True,
        )

        logger.info("User %s completed onboarding", user_id)
        return {"step": 5, "status": "ok", "onboarding_complete": True}

    else:
        raise HTTPException(status_code=400, detail=f"Invalid step number: {step_number}")


@router.post("/complete", response_model=OnboardingCompleteResponse, summary="Complete onboarding in one call")
async def complete_onboarding(
    req: OnboardingCompleteRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_user),
):
    """
    Complete all onboarding steps in one call.
    Creates user_memory, marks onboarding_complete, and returns a new token.
    """
    user_id = str(current_user["_id"])
    now = datetime.datetime.now(datetime.UTC)
    age_group = _age_group(req.age)
    nickname = req.nickname or req.name

    # Update user
    await db.users.update_one(
        document_id_filter(user_id),
        {
            "$set": {
                "name": req.name,
                "nickname": nickname,
                "age": req.age,
                "age_group": age_group,
                "onboarding_people": req.people,
                "checkin_preferred_time": req.checkin_preferred_time,
                "onboarding_complete": True,
                "updated_at": now,
            }
        },
    )

    # Create user_memory
    people_graph = _build_people_graph(req.people)
    await db.user_memory.update_one(
        {"user_id": user_id},
        {
            "$setOnInsert": {
                "user_id": user_id,
                "display_name": f"{nickname}'s Memory",
                "created_at": now,
            },
            "$set": {
                "profile": {
                    "name": req.name,
                    "nickname": nickname,
                    "age": req.age,
                    "age_group": age_group,
                    "onboarding_complete": True,
                },
                "people": people_graph,
                "preferences": {
                    "checkin_preferred_time": req.checkin_preferred_time,
                    "music_genres": [],
                    "mindfulness_style": "",
                    # No introvert_score here — memory_recall.py's own
                    # invariant is "None means nothing has been inferred yet,
                    # which is different from a genuine 0.5". PersonalityAgent
                    # is what's supposed to set this, from what a user
                    # actually says across sessions; a hardcoded 0.5 at
                    # onboarding was indistinguishable from a real inference
                    # and showed up on the Memory page's "Social read" card
                    # captioned "picked up from conversation" before any
                    # conversation had happened.
                    "preferred_modality": "CBT",
                    "personality": req.personality,
                    "tone_preference": req.tone_preference or "balanced",
                },
                "emotional_patterns": {
                    "most_common_emotion": None,
                    "average_distress": 0.0,
                    "trigger_topics": [],
                    "effective_coping": [],
                },
                "milestones": ["Completed onboarding"],
                "raw_notes": [],
                "updated_at": now,
            },
        },
        upsert=True,
    )

    # Create first session
    import uuid
    session_id = str(uuid.uuid4())
    await db.sessions.insert_one({
        "session_id": session_id,
        "user_id": user_id,
        "title": "First Session",
        "started_at": now,
        "ended_at": None,
        "status": "active",
        "turns": [],
        "eos_timeline": [],
        "agents_used": [],
        "primary_modality": None,
    })

    # Generate new token
    user = await db.users.find_one(document_id_filter(user_id))
    role = user.get("role", settings.USER_ROLE_NAME)
    tokens = create_token_pair(user_id, user.get("email", ""), role=role)

    logger.info("User %s completed full onboarding, session %s created", user_id, session_id)

    return OnboardingCompleteResponse(
        user_id=user_id,
        onboarding_complete=True,
        session_id=session_id,
        access_token=tokens["access_token"],
        token_type="bearer",
        expires_in=tokens["expires_in"],
    )
