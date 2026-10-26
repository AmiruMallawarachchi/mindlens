# tests/unit/models/test_loader.py
"""Unit tests for ModelManager singleton and pipeline loading."""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest
from app.models.loader import ModelManager


class TestCrossEncoderRerank:
    """T1 â€” ModelManager.rerank is the boundary the retriever scores through."""

    @staticmethod
    def _health(mgr: ModelManager) -> dict:
        return object.__getattribute__(mgr, "_health")

    def test_pairs_are_sent_in_one_batched_call(self) -> None:
        """One call with {text, text_pair} pairs â€” not one call per chunk."""
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

