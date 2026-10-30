"""Global pytest configuration and shared fixtures."""

from __future__ import annotations

import datetime
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock  # noqa: F401

import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.core.emotional_os import (
    EmotionalOperatingState,
    Modality,
)

# ============================================================
# ASYNC CONFIGURATION
# ============================================================

# Fixture modules are registered as plugins rather than imported into each
# test module: importing a fixture and then accepting a same-named parameter
# is a redefinition to linters, and ruff's unused-import fix would delete a
# fixture the tests still need.
pytest_plugins = (
    "pytest_asyncio",
    "tests.unit.routers.chat_test_fixtures",
    "tests.unit.routers.session_test_fixtures",
)


# ============================================================
# CORE MODEL FIXTURES
# ============================================================


@pytest.fixture
def default_eos() -> EmotionalOperatingState:
    """Fresh EOS with neutral defaults."""
    return EmotionalOperatingState()


@pytest.fixture
def high_distress_eos() -> EmotionalOperatingState:
    """EOS simulating acute crisis state."""
    return EmotionalOperatingState(
        surface_emotion="fear",
        core_emotion="fear",
        suppressed_emotion="anger",
        emotional_stability=0.1,
        mental_fatigue=0.8,
        social_energy=0.2,
        distress_level=0.9,
        trust_level=0.2,
        valence="negative",
        modality=Modality.DBT,
        run_mindfulness=True,
        session_depth=0.7,
        alliance_score=0.3,
    )


@pytest.fixture
def stable_eos() -> EmotionalOperatingState:
    """EOS simulating stable, trusting state ready for challenge."""
    return EmotionalOperatingState(
        surface_emotion="joy",
        core_emotion="contentment",
        suppressed_emotion=None,
        emotional_stability=0.8,
        mental_fatigue=0.3,
        social_energy=0.7,
        distress_level=0.2,
        trust_level=0.8,
        valence="positive",
        modality=Modality.CBT,
        run_challenge=True,
        session_depth=0.6,
        alliance_score=0.7,
    )


# ============================================================
# DATABASE FIXTURES
# ============================================================


@pytest.fixture
def mock_db() -> MagicMock:
    """Mock MongoDB database for unit tests."""
    mock = MagicMock()
    mock.users = MagicMock()
    mock.sessions = MagicMock()
    mock.token_blocklist = MagicMock()
    mock.user_memory = MagicMock()
    mock.mood_logs = MagicMock()
    mock.safety_events = MagicMock()
    mock.audit_log = MagicMock()
    mock.pending_checkins = MagicMock()
    mock.journal_entries = MagicMock()
    mock.progress_insights = MagicMock()
    mock.users.find_one = AsyncMock(
        return_value={
            "_id": "user_123",
            "email": "test@example.com",
            "name": "Test User",
            "nickname": "Test",
            "age": 22,
            "age_group": "adult",
            "role": "user",
            "is_active": True,
            "onboarding_complete": True,
            "created_at": datetime.datetime.now(datetime.UTC),
        }
    )
    mock.token_blocklist.find_one = AsyncMock(return_value=None)
    return mock


@pytest.fixture
async def test_client() -> Any:
    """Async HTTP client for router testing."""
    from app.main import app
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
