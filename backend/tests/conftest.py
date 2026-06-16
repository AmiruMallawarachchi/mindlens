"""Global pytest configuration and shared fixtures."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.core.emotional_os import EmotionalOperatingState
from app.models.loader import ModelManager

# ========================================================
# ASYNC CONFIGURATION
# ========================================================

pytest_plugins = ("pytest_asyncio",)


# ========================================================
# CORE MODEL FIXTURES
# ========================================================

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
        emotional_stability=0.1,
        mental_fatigue=0.8,
        social_energy=0.2,
        distress_level=0.9,
        trust_level=0.2,
        valence="negative",
        modality="DBT",
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
        emotional_stability=0.8,
        mental_fatigue=0.3,
        social_energy=0.7,
        distress_level=0.2,
        trust_level=0.8,
        valence="positive",
        modality="CBT",
        run_challenge=True,
        session_depth=0.6,
        alliance_score=0.7,
    )


# ========================================================
# MODEL MANAGER FIXTURE
# ========================================================

@pytest.fixture
def mock_model_manager() -> MagicMock:
    """ModelManager with mocked pipelines (no GPU needed)."""
    manager = MagicMock(spec=ModelManager)

    # predict_emotion → 28-class go-emotions output (list[list[dict]])
    async def mock_predict_emotion(text: str) -> list[list[dict[str, Any]]]:
        return [[
            {"label": "LABEL_25", "score": 0.85},  # sadness
            {"label": "LABEL_19", "score": 0.6},   # nervousness
            {"label": "LABEL_17", "score": 0.1},   # joy
        ]]

    # predict_crisis → binary output (list[dict])
    async def mock_predict_crisis(text: str) -> list[dict[str, Any]]:
        return [{"label": "NON_CRISIS", "score": 0.12}]

    # predict_mental_health → multi-label output (list[list[dict]])
    async def mock_predict_mental_health(text: str) -> list[list[dict[str, Any]]]:
        return [[
            {"label": "LABEL_1", "score": 0.7},  # anxiety
            {"label": "LABEL_0", "score": 0.3},  # depression
        ]]

    # predict_all → combined
    async def mock_predict_all(text: str) -> dict[str, list[Any]]:
        return {
            "emotion": await mock_predict_emotion(text),
            "crisis": await mock_predict_crisis(text),
            "mental_health": await mock_predict_mental_health(text),
        }

    manager.predict_emotion = mock_predict_emotion
    manager.predict_crisis = mock_predict_crisis
    manager.predict_mental_health = mock_predict_mental_health
    manager.predict_all = mock_predict_all

    return manager


# ========================================================
# FASTAPI TEST CLIENT
# ========================================================

@pytest.fixture
async def test_client() -> Any:
    """Async HTTP client for router testing."""
    from httpx import AsyncClient
    from app.main import app

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


# ========================================================
# DATABASE FIXTURES
# ========================================================

@pytest.fixture
async def test_db() -> Any:
    """Isolated test database."""
    from app.db import Database

    db = Database()
    yield db
    # Cleanup