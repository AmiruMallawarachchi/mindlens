"""Shared fixtures for focused WebSocket chat service tests."""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_db_ws():
    """Mock DB for WebSocket persistence tests."""
    mock = MagicMock()
    mock.users = MagicMock()
    mock.sessions = MagicMock()
    mock.token_blocklist = MagicMock()
    mock.pending_checkins = MagicMock()
    mock.safety_events = MagicMock()
    mock.mood_logs = MagicMock()
    mock.mood_logs.insert_one = AsyncMock()
    return mock


@pytest.fixture
def sample_session_doc() -> dict[str, Any]:
    return {
        "session_id": "sess_abc",
        "user_id": "user_123",
        "title": "Exam stress",
        "started_at": datetime.datetime.now(datetime.UTC),
        "ended_at": None,
        "status": "active",
        "turns": [],
        "eos_timeline": [],
        "agents_used": [],
        "primary_modality": None,
    }
