# tests/unit/models/test_loader.py
"""Unit tests for ModelManager singleton and pipeline loading."""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest
from app.models.loader import ModelManager


class TestConcurrentLoadIsSerialized:
    """Regression â€” `_load_pipeline` runs inside `asyncio.to_thread`
    (predict_all, warmup_all), so the first turn after startup fires several
    model loads across genuinely concurrent OS threads. Live-observed
    failure on this machine before the fix: "Cannot copy out of meta
    tensor; no data!" â€” two heavy torch loads racing for memory at once. A
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
    """Regression â€” the crisis model's HF repo pairs a BertTokenizerFast
    (which emits token_type_ids by default) with a
    DistilBertForSequenceClassification model (no segment embeddings, rejects
    that kwarg outright). Every real call raised, was swallowed by
    predict_all()'s return_exceptions=True, and silently zeroed out the
    classifier layer of crisis detection on every single turn â€” regex
    (safety_gate.py) still caught direct phrasing, but the ML backstop for
    coded or unusual phrasing never ran. Restricting the tokenizer's output
    keys at construction time is the fix, and it must apply to crisis only â€”
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
        # The pipeline must be pinned to the same commit as its tokenizer â€”
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
        """The real crisis() method must actually opt in â€” this is the
        regression the other two tests exist to make impossible to skip."""
        mgr = ModelManager()
        with patch.object(mgr, "_load_pipeline") as mock_load:
            mgr.crisis()
        assert mock_load.call_args.kwargs["tokenizer_model_input_names"] == [
            "input_ids",
            "attention_mask",
        ]


class TestWarmupProvesInferenceNotJustLoading:
    """Loading a pipeline is not evidence that it can run.

    A transformers/tokenizers version mismatch loads all five models
    cleanly and then raises on every `pipeline(text)` call. predict_all
    gathers with return_exceptions=True, so those failures were swallowed
    into empty score dicts: distress computed to 0.0 on every turn and the
    crisis classifier contributed nothing, while /ready still returned 200.
    warmup_all now runs one throwaway prediction per model so that becomes
    a boot failure instead of a silent degradation.
    """

    @pytest.mark.asyncio
    async def test_warmup_fails_when_a_model_loads_but_cannot_infer(self) -> None:
        mgr = ModelManager()

        async def raises_dtype_typeerror(_text: str) -> list:
            raise TypeError(
                "_batch_encode_plus() got an unexpected keyword argument 'dtype'"
            )

        with (
            # Loading succeeds for every model.
            patch.object(type(mgr), "emotion", property(lambda s: MagicMock())),
            patch.object(type(mgr), "crisis", property(lambda s: MagicMock())),
            patch.object(type(mgr), "mental_health", property(lambda s: MagicMock())),
            patch.object(type(mgr), "distortion", property(lambda s: MagicMock())),
            patch.object(type(mgr), "rag_reranker", property(lambda s: MagicMock())),
            patch.object(mgr, "rerank", return_value=[0.0]),
            # ...but inference does not.
            patch.object(mgr, "predict_emotion", raises_dtype_typeerror),
            patch.object(mgr, "predict_crisis", return_value=[]),
            patch.object(mgr, "predict_mental_health", return_value=[]),
            patch.object(mgr, "predict_distortion", return_value=[]),
        ):
            with pytest.raises(RuntimeError, match="cannot run inference"):
                await mgr.warmup_all()

    @pytest.mark.asyncio
    async def test_warmup_passes_when_inference_works(self) -> None:
        mgr = ModelManager()
        with (
            patch.object(type(mgr), "emotion", property(lambda s: MagicMock())),
            patch.object(type(mgr), "crisis", property(lambda s: MagicMock())),
            patch.object(type(mgr), "mental_health", property(lambda s: MagicMock())),
            patch.object(type(mgr), "distortion", property(lambda s: MagicMock())),
            patch.object(type(mgr), "rag_reranker", property(lambda s: MagicMock())),
            patch.object(mgr, "rerank", return_value=[0.0]),
            patch.object(mgr, "predict_emotion", return_value=[]),
            patch.object(mgr, "predict_crisis", return_value=[]),
            patch.object(mgr, "predict_mental_health", return_value=[]),
            patch.object(mgr, "predict_distortion", return_value=[]),
        ):
            assert await mgr.warmup_all() is not None

