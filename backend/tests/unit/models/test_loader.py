# tests/unit/models/test_loader.py
"""Unit tests for ModelManager singleton and pipeline loading."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from app.models import loader
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


class TestRenderFreeModelMode:
    """Render Free keeps classifier memory bounded and honest."""

    @pytest.fixture(autouse=True)
    def reset_manager(self) -> None:
        mgr = ModelManager()
        object.__setattr__(mgr, "_pipelines", {})
        object.__setattr__(mgr, "_health", {})
        object.__setattr__(mgr, "_resident_model", None)

    def test_only_one_model_can_be_resident(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(loader.settings, "deployment_mode", "render_free_demo")
        monkeypatch.setattr(loader.settings, "model_backend", "pytorch")
        mgr = ModelManager()

        def fake_loader(*args: Any, **kwargs: Any) -> MagicMock:
            pipe = MagicMock()
            pipe.return_value = [{"label": "LABEL_0", "score": 0.9}]
            return pipe

        with patch.object(mgr, "_load_pytorch_pipeline", side_effect=fake_loader):
            mgr.emotion()
            assert mgr.resident_model_count() == 1
            mgr.crisis()
            assert mgr.resident_model_count() == 1
            health = mgr.health_status()
            assert health["emotion"]["status"] == "unloaded"
            assert health["crisis"]["status"] == "ready"

    @pytest.mark.asyncio
    async def test_model_failure_degrades_safely(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(loader.settings, "deployment_mode", "render_free_demo")
        mgr = ModelManager()

        with patch.object(mgr, "emotion", side_effect=RuntimeError("missing model")):
            result = await mgr.predict_emotion("hello")

        assert result == []
        assert mgr.health_status()["emotion"]["status"] == "error"

    @pytest.mark.asyncio
    async def test_successful_free_inference_unloads_model(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(loader.settings, "deployment_mode", "render_free_demo")
        monkeypatch.setattr(loader.settings, "model_backend", "pytorch")
        mgr = ModelManager()
        pipe = MagicMock()
        pipe.return_value = [{"label": "LABEL_0", "score": 0.95}]

        with patch.object(mgr, "_load_pytorch_pipeline", return_value=pipe):
            result = await mgr.predict_emotion("hello")

        assert result[0]["label"] == "LABEL_0"
        assert mgr.resident_model_count() == 0
        assert mgr.health_status()["emotion"]["status"] == "unloaded"
