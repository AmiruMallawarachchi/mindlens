"""Onboarding profile helpers and read operations."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db import document_id_filter
from app.routers.onboarding_schemas import OnboardingStatusResponse


def age_group(age: int) -> str:
    return "teen" if age <= 19 else "adult"


def build_people_graph(people: list[dict[str, str]]) -> dict[str, Any]:
    graph = {}
    for person in people:
        name = person.get("name", "").strip()
        if not name:
            continue
        graph[name] = {
            "role": person.get("role", ""),
            "context": person.get("context", ""),
            "sentiment": "positive",
        }
    return graph


async def get_onboarding_status_data(
    user_id: str, db: AsyncIOMotorDatabase
) -> OnboardingStatusResponse:
    """Load and shape the current user's onboarding progress."""
    user = await db.users.find_one(document_id_filter(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

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
