# tests/unit/models/test_loader.py
"""Unit tests for ModelManager singleton and pipeline loading."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from app.models.loader import ModelManager


class TestModelManagerSingleton:
    """Verify singleton behavior."""

    def test_same_instance(self) -> None:
        """Multiple calls return the same object."""
        a = ModelManager()
        b = ModelManager()
        assert a is b

    def test_pipelines_dict_exists(self) -> None:
        """Singleton initializes internal storage."""
        mgr = ModelManager()
        pipelines = object.__getattribute__(mgr, "_pipelines")
        assert isinstance(pipelines, dict)


class TestModelManagerAsyncPredictors:
    """Mocked pipeline inference."""

    @pytest.fixture
    def mock_pipeline(self) -> MagicMock:
        p = MagicMock()
        p.return_value = [{"label": "LABEL_0", "score": 0.95}]
        return p

    @pytest.mark.asyncio
    async def test_predict_emotion(self, mock_pipeline: MagicMock) -> None:
        """Emotion prediction returns structured output."""
        mgr = ModelManager()
        with patch.object(mgr, "emotion", return_value=mock_pipeline):
            result = await mgr.predict_emotion("test")
            assert isinstance(result, list)
            assert result[0]["label"] == "LABEL_0"

    @pytest.mark.asyncio
    async def test_predict_all_returns_classifier_keys(self) -> None:
        """predict_all returns all per-turn classifier outputs."""
        mgr = ModelManager()
        with (
            patch.object(mgr, "predict_emotion", return_value=[{"s": 1}]),
            patch.object(mgr, "predict_crisis", return_value=[{"s": 2}]),
            patch.object(mgr, "predict_mental_health", return_value=[{"s": 3}]),
            patch.object(mgr, "predict_distortion", return_value=[{"s": 4}]),
        ):
            result = await mgr.predict_all("text")
            assert set(result.keys()) == {
                "emotion",
                "crisis",
                "mental_health",
                "distortion",
            }
