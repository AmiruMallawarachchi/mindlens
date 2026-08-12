# tests/unit/models/test_loader.py
"""Unit tests for ModelManager singleton and pipeline loading."""

from __future__ import annotations

import threading
import time
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


class TestCrossEncoderRerank:
    """T1 — ModelManager.rerank is the boundary the retriever scores through."""

    @staticmethod
    def _health(mgr: ModelManager) -> dict:
        return object.__getattribute__(mgr, "_health")

    def test_pairs_are_sent_in_one_batched_call(self) -> None:
        """One call with {text, text_pair} pairs — not one call per chunk."""
        calls: list = []

        def pipe(pairs):
            calls.append(pairs)
            return [[{"label": "LABEL_0", "score": 0.5}] for _ in pairs]

        mgr = ModelManager()
        docs = ["a", "b", "c"]
        with patch.object(mgr, "rag_reranker", return_value=pipe):
            scores = mgr.rerank("query", docs)

        assert len(calls) == 1, "reranker was invoked once per document"
        assert [p["text_pair"] for p in calls[0]] == docs
        assert all(p["text"] == "query" for p in calls[0])
        assert scores == [0.5, 0.5, 0.5]

    def test_records_last_inference_ms(self) -> None:
        """The admin Model drawer reads this; without it the model looks unused."""
        mgr = ModelManager()
        self._health(mgr).pop("rag_reranker", None)
        pipe = MagicMock(return_value=[[{"label": "LABEL_0", "score": 0.9}]])

        with patch.object(mgr, "rag_reranker", return_value=pipe):
            mgr.rerank("query", ["only"])

        entry = self._health(mgr)["rag_reranker"]
        assert entry["last_inference_ms"] is not None
        assert entry["status"] == "ready"

    def test_bare_dict_results_are_accepted(self) -> None:
        """The pipeline drops the wrapping list when top_k is unset."""
        mgr = ModelManager()
        pipe = MagicMock(return_value=[{"label": "LABEL_0", "score": 0.7}])
        with patch.object(mgr, "rag_reranker", return_value=pipe):
            assert mgr.rerank("query", ["only"]) == [0.7]

    def test_empty_documents_short_circuits(self) -> None:
        mgr = ModelManager()
        pipe = MagicMock()
        with patch.object(mgr, "rag_reranker", return_value=pipe):
            assert mgr.rerank("query", []) == []
        pipe.assert_not_called()

    def test_failure_raises_and_counts_the_error(self) -> None:
        """The retriever owns the fallback decision, so this must raise."""
        mgr = ModelManager()
        before = self._health(mgr).get("rag_reranker", {}).get("error_count", 0)

        with patch.object(mgr, "rag_reranker", side_effect=RuntimeError("boom")):
            with pytest.raises(RuntimeError):
                mgr.rerank("query", ["a"])

        assert self._health(mgr)["rag_reranker"]["error_count"] == before + 1

    def test_score_count_mismatch_is_rejected(self) -> None:
        mgr = ModelManager()
        pipe = MagicMock(return_value=[[{"label": "LABEL_0", "score": 0.5}]])
        with patch.object(mgr, "rag_reranker", return_value=pipe):
            with pytest.raises(ValueError):
                mgr.rerank("query", ["a", "b"])


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


class TestConcurrentLoadIsSerialized:
    """Regression — `_load_pipeline` runs inside `asyncio.to_thread`
    (predict_all, warmup_all), so the first turn after startup fires several
    model loads across genuinely concurrent OS threads. Live-observed
    failure on this machine before the fix: "Cannot copy out of meta
    tensor; no data!" — two heavy torch loads racing for memory at once. A
    class-level `_load_lock` existed but was never acquired anywhere; this
    verifies it now actually serializes the loading section."""

    @pytest.fixture
    def probe_name(self) -> str:
        name = "test_probe_concurrent_load"
        mgr = ModelManager()
        pipelines = object.__getattribute__(mgr, "_pipelines")
        health = object.__getattribute__(mgr, "_health")
        pipelines.pop(name, None)
        health.pop(name, None)
        yield name
        pipelines.pop(name, None)
        health.pop(name, None)

    def test_two_threads_loading_the_same_model_never_overlap(
        self, probe_name: str
    ) -> None:
        mgr = ModelManager()
        overlap_detected = threading.Event()
        currently_loading = threading.Event()

        def slow_pipeline_factory(*args: object, **kwargs: object) -> MagicMock:
            if currently_loading.is_set():
                overlap_detected.set()
            currently_loading.set()
            time.sleep(0.05)
            currently_loading.clear()
            return MagicMock()

        with patch("app.models.loader.pipeline", side_effect=slow_pipeline_factory):
            threads = [
                threading.Thread(
                    target=mgr._load_pipeline, args=(probe_name, "some/model", "text-classification")
                )
                for _ in range(4)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)

        assert not overlap_detected.is_set(), "two threads built a pipeline at the same time"
        # All four calls resolve to the one cached pipeline, not four builds.
        pipelines = object.__getattribute__(mgr, "_pipelines")
        assert probe_name in pipelines


class TestCrisisTokenizerMismatchFix:
    """Regression — the crisis model's HF repo pairs a BertTokenizerFast
    (which emits token_type_ids by default) with a
    DistilBertForSequenceClassification model (no segment embeddings, rejects
    that kwarg outright). Every real call raised, was swallowed by
    predict_all()'s return_exceptions=True, and silently zeroed out the
    classifier layer of crisis detection on every single turn — regex
    (safety_gate.py) still caught direct phrasing, but the ML backstop for
    coded or unusual phrasing never ran. Restricting the tokenizer's output
    keys at construction time is the fix, and it must apply to crisis only —
    mental_health and rag_reranker are real BERT models that correctly need
    token_type_ids."""

    @pytest.fixture
    def probe_name(self) -> str:
        name = "test_probe_crisis_tokenizer"
        mgr = ModelManager()
        pipelines = object.__getattribute__(mgr, "_pipelines")
        health = object.__getattribute__(mgr, "_health")
        pipelines.pop(name, None)
        health.pop(name, None)
        yield name
        pipelines.pop(name, None)
        health.pop(name, None)

    def test_requested_tokenizer_is_restricted_to_the_supported_inputs(
        self, probe_name: str
    ) -> None:
        mgr = ModelManager()
        with (
            patch("app.models.loader.AutoTokenizer") as mock_auto_tok,
            patch("app.models.loader.pipeline") as mock_pipeline,
        ):
            mock_auto_tok.from_pretrained.return_value = MagicMock()
            mgr._load_pipeline(
                probe_name,
                "some/model",
                "text-classification",
                tokenizer_model_input_names=["input_ids", "attention_mask"],
            )

        mock_auto_tok.from_pretrained.assert_called_once_with(
            "some/model",
            revision="main",
            model_input_names=["input_ids", "attention_mask"],
        )
        assert (
            mock_pipeline.call_args.kwargs["tokenizer"]
            is mock_auto_tok.from_pretrained.return_value
        )
        # The pipeline must be pinned to the same commit as its tokenizer —
        # fetching the two from different revisions is how you get a tokenizer
        # and a model that disagree about the vocabulary.
        assert mock_pipeline.call_args.kwargs["revision"] == "main"

    def test_a_model_without_the_flag_gets_the_plain_string_tokenizer(
        self, probe_name: str
    ) -> None:
        mgr = ModelManager()
        with (
            patch("app.models.loader.AutoTokenizer") as mock_auto_tok,
            patch("app.models.loader.pipeline") as mock_pipeline,
        ):
            mgr._load_pipeline(probe_name, "some/model", "text-classification")

        mock_auto_tok.from_pretrained.assert_not_called()
        assert mock_pipeline.call_args.kwargs["tokenizer"] == "some/model"

    def test_crisis_requests_the_restricted_tokenizer(self) -> None:
        """The real crisis() method must actually opt in — this is the
        regression the other two tests exist to make impossible to skip."""
        mgr = ModelManager()
        with patch.object(mgr, "_load_pipeline") as mock_load:
            mgr.crisis()
        assert mock_load.call_args.kwargs["tokenizer_model_input_names"] == [
            "input_ids",
            "attention_mask",
        ]
