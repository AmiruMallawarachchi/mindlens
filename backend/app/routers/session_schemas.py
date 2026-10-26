"""Request and response models for session routes."""

from __future__ import annotations

import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class SessionCreateRequest(BaseModel):
    """Optional metadata when creating a session."""

    title: str | None = Field(None, max_length=200)
    context: str | None = Field(None, max_length=500)


class SessionCreateResponse(BaseModel):
    """Response after creating a session."""

    session_id: str
    user_id: str
    title: str | None
    started_at: datetime.datetime
    status: str


class SessionListItem(BaseModel):
    """Summary of a session for listing."""

    session_id: str
    title: str | None
    started_at: datetime.datetime
    ended_at: datetime.datetime | None
    status: str
    turn_count: int
    primary_modality: str | None
    pinned: bool = False


class SessionDetailResponse(BaseModel):
    """Full session detail including transcript."""

    session_id: str
    user_id: str
    title: str | None
    started_at: datetime.datetime
    ended_at: datetime.datetime | None
    status: str
    turns: list[dict[str, Any]]
    eos_timeline: list[dict[str, Any]]
    agents_used: list[str]
    primary_modality: str | None
    pinned: bool = False


class SessionPinRequest(BaseModel):
    """Body for PATCH /{session_id}/pin."""

    pinned: bool


class SessionRenameRequest(BaseModel):
    """Body for PATCH /{session_id}/title."""

    title: str = Field(min_length=1, max_length=200)

    @field_validator("title")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        """A title of spaces would render as an empty sidebar row that still
        suppresses the date fallback, so it is rejected rather than stored."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Title cannot be blank")
        return cleaned


class SessionDeleteResponse(BaseModel):
    """Response after permanently deleting a session."""

    session_id: str
    # Per-collection counts, so the caller can see what was actually removed
    # rather than trust that something was.
    deleted: dict[str, int]


