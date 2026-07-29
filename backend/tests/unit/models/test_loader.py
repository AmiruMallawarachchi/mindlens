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


class TestModelManagerHealthErrorCount:
    """SYSTEM.md §13.4's admin Model Health Drawer requires an error count.
    Before this, each failure overwrote the health entry outright, so only
    the most recent error was ever visible.

    ModelManager is a true process-wide singleton, so each test claims a
    private probe name and cleans it out of `_health` afterward rather than
    touching one of the five real configured models — those are shared
    state with every other test in the session.
    """

    @pytest.fixture
    def probe_name(self) -> str:
        name = "test_probe_error_count"
        mgr = ModelManager()
        health = object.__getattribute__(mgr, "_health")
        health.pop(name, None)
        yield name
        health.pop(name, None)

    def test_record_error_starts_at_one(self, probe_name: str) -> None:
        mgr = ModelManager()
        entry = mgr._record_error(probe_name, ValueError("boom"))
        assert entry["error_count"] == 1
        assert entry["status"] == "error"
        assert entry["error"] == "ValueError"

    def test_record_error_accumulates_across_calls(self, probe_name: str) -> None:
        mgr = ModelManager()
        mgr._record_error(probe_name, ValueError("first"))
        mgr._record_error(probe_name, RuntimeError("second"))
        entry = mgr._record_error(probe_name, RuntimeError("third"))
        assert entry["error_count"] == 3
        assert entry["error"] == "RuntimeError"

    @pytest.mark.asyncio
    async def test_predict_failure_increments_error_count(self, probe_name: str) -> None:
        mgr = ModelManager()

        def failing_accessor() -> MagicMock:
            raise RuntimeError("model unavailable")

        with pytest.raises(RuntimeError):
            await mgr._predict(probe_name, failing_accessor, "text")

        health = object.__getattribute__(mgr, "_health")
        assert health[probe_name]["error_count"] == 1

        with pytest.raises(RuntimeError):
            await mgr._predict(probe_name, failing_accessor, "text")
        assert health[probe_name]["error_count"] == 2

    @pytest.mark.asyncio
    async def test_recovery_preserves_count_and_clears_error(self, probe_name: str) -> None:
        """A model that failed twice and then recovered should show
        status=ready with error=None, but the error_count must survive —
        it's a running total, not "is there currently a problem"."""
        mgr = ModelManager()

        def failing_accessor() -> MagicMock:
            raise RuntimeError("down")

        with pytest.raises(RuntimeError):
            await mgr._predict(probe_name, failing_accessor, "text")
        with pytest.raises(RuntimeError):
            await mgr._predict(probe_name, failing_accessor, "text")

        working_pipeline = MagicMock(return_value=[{"label": "LABEL_0", "score": 0.9}])
        await mgr._predict(probe_name, lambda: working_pipeline, "text")

        health = object.__getattribute__(mgr, "_health")
        assert health[probe_name]["status"] == "ready"
        assert health[probe_name]["error"] is None
        assert health[probe_name]["error_count"] == 2

    def test_health_status_defaults_error_count_to_zero(self) -> None:
        """A configured model untouched this process still reports
        error_count=0 rather than omitting the field."""
        mgr = ModelManager()
        health = object.__getattribute__(mgr, "_health")
        removed = health.pop("emotion", None)
        try:
            status = mgr.health_status()
            assert status["emotion"]["error_count"] == 0
        finally:
            if removed is not None:
                health["emotion"] = removed
