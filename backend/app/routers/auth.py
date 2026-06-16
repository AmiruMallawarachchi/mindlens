# backend/app/routers/auth.py
"""Authentication router — JWT login/register."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.post("/register")
async def register() -> dict[str, str]:
    return {"status": "stub"}


@router.post("/login")
async def login() -> dict[str, str]:
    return {"status": "stub"}