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
from app.models.loader import ModelManager

# ============================================================
# ASYNC CONFIGURATION
# ============================================================

pytest_plugins = ("pytest_asyncio",)


# ============================================================
# AGENT CONTEXT FIXTURES
# ============================================================


@pytest.fixture
def agent_context(default_eos: EmotionalOperatingState) -> Any:
    """Standard AgentContext for agent testing."""
    from app.agents.base_agent import AgentContext

    return AgentContext(
        eos=default_eos,
        user_text="I feel anxious about my exam tomorrow.",
        user_name="Amiru",
        session_history=[],
        rag_chunks=[],
    )


@pytest.fixture
def crisis_agent_context(high_distress_eos: EmotionalOperatingState) -> Any:
    """AgentContext for crisis testing."""
    from app.agents.base_agent import AgentContext

    return AgentContext(
        eos=high_distress_eos,
        user_text="I want to end my life",
        user_name="Amiru",
        session_history=[],
        rag_chunks=[],
    )


@pytest.fixture
def stable_agent_context(stable_eos: EmotionalOperatingState) -> Any:
    """AgentContext for stable/trusting user testing."""
    from app.agents.base_agent import AgentContext

    return AgentContext(
        eos=stable_eos,
        user_text="I had a good day today, but I'm still worried about my project.",
        user_name="Amiru",
        session_history=[],
        rag_chunks=[],
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
# MODEL MANAGER FIXTURE
# ============================================================


@pytest.fixture
def mock_model_manager() -> MagicMock:
    """ModelManager with mocked pipelines (no GPU needed)."""
    manager = MagicMock(spec=ModelManager)

    async def mock_predict_emotion(text: str) -> list[list[dict[str, Any]]]:
        return [[
            {"label": "LABEL_25", "score": 0.85},
            {"label": "LABEL_19", "score": 0.6},
            {"label": "LABEL_17", "score": 0.1},
        ]]

    async def mock_predict_crisis(text: str) -> list[dict[str, Any]]:
        return [{"label": "NON_CRISIS", "score": 0.12}]

    async def mock_predict_mental_health(text: str) -> list[list[dict[str, Any]]]:
        return [[
            {"label": "LABEL_1", "score": 0.7},
            {"label": "LABEL_0", "score": 0.3},
        ]]

    async def mock_predict_all(text: str) -> dict[str, list[Any]]:
        return {
            "emotion": await mock_predict_emotion(text),
            "crisis": await mock_predict_crisis(text),
            "mental_health": await mock_predict_mental_health(text),
            "distortion": [],
        }

    manager.predict_emotion = mock_predict_emotion
    manager.predict_crisis = mock_predict_crisis
    manager.predict_mental_health = mock_predict_mental_health
    manager.predict_all = mock_predict_all

    return manager


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
