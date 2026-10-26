"""Cross-encoder reranking coverage for the local therapy retriever."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from app.agents.groq_client import begin_degradation_tracking
from app.config import settings
from app.core.emotional_os import EmotionalOperatingState, Modality
from app.rag.retriever import RERANKER_DEGRADED, TherapyRetriever
class TestCrossEncoderReranking:
    """T1 â€” the fine-tuned cross-encoder actually orders retrieval."""

    #: MMR hands these back in this order; the reranker disagrees.
    DOCS = ["mmr first", "mmr second", "mmr third"]
    #: Scores keyed by document â€” "mmr third" is the genuinely relevant one.
    SCORES = {"mmr first": 0.11, "mmr second": 0.42, "mmr third": 0.97}

    @pytest.fixture
    def mock_store(self):
        store = MagicMock()
        store.connect = MagicMock()
        store.query_mmr.return_value = {
            "documents": [list(self.DOCS)],
            # Deliberately no age-group signal, so the cross-encoder is the
            # only thing that can reorder these.
            "metadatas": [[{"category": "CBT", "tags": ""} for _ in self.DOCS]],
            "ids": [["id1", "id2", "id3"]],
            "distances": [[0.1, 0.2, 0.3]],
        }
        return store

    @pytest.fixture
    def scoring_manager(self):
        manager = MagicMock()
        manager.rerank.side_effect = lambda query, docs: [self.SCORES[d] for d in docs]
        return manager

    @staticmethod
    def _eos() -> EmotionalOperatingState:
        # "adult" against metadata carrying no adult keywords, so the age
        # heuristic scores every candidate 0 and the cross-encoder is the only
        # thing that can reorder them.
        return EmotionalOperatingState(
            surface_emotion="anxiety", modality=Modality.CBT, age_group="adult"
        )

    def test_reranker_reorders_and_top_result_is_highest_scored(
        self, mock_store: MagicMock, scoring_manager: MagicMock
    ) -> None:
        retriever = TherapyRetriever(
            vector_store=mock_store, k=3, fetch_k=10, model_manager=scoring_manager
        )
        chunks = retriever.retrieve("exam panic", self._eos())

        assert chunks != self.DOCS, "reranking left MMR order untouched"
        assert chunks[0] == "mmr third", "top result is not the highest-scored pair"
        assert chunks == ["mmr third", "mmr second", "mmr first"]

    def test_every_candidate_is_scored_in_one_call(
        self, mock_store: MagicMock
    ) -> None:
        """The whole candidate set goes to the reranker at once.

        Batching *within* the pipeline call is asserted at the ModelManager
        boundary â€” see tests/unit/models/test_loader.py.
        """
        calls: list[Any] = []

        def rerank(query, docs):
            calls.append((query, docs))
            return [0.5] * len(docs)

        manager = MagicMock()
        manager.rerank.side_effect = rerank
        retriever = TherapyRetriever(
            vector_store=mock_store, k=3, fetch_k=10, model_manager=manager
        )
        retriever.retrieve("exam panic", self._eos())

        assert len(calls) == 1, "reranker was called once per chunk"
        assert calls[0][1] == self.DOCS

    def test_fetches_fetch_k_candidates_not_k(self, mock_store: MagicMock) -> None:
        """Reranking only the final k would waste the model."""
        manager = MagicMock()
        manager.rerank.side_effect = lambda query, docs: [0.5] * len(docs)
        retriever = TherapyRetriever(
            vector_store=mock_store, k=3, fetch_k=20, model_manager=manager
        )
        retriever.retrieve("exam panic", self._eos())

        assert mock_store.query_mmr.call_args.kwargs["n_results"] == 20

    def test_reranker_failure_falls_back_to_mmr_order_and_marks_degraded(
        self, mock_store: MagicMock
    ) -> None:
        """A reranker fault must never fail a chat turn."""
        manager = MagicMock()
        manager.rerank.side_effect = RuntimeError("model unavailable")
        retriever = TherapyRetriever(
            vector_store=mock_store, k=3, fetch_k=10, model_manager=manager
        )

        sink = begin_degradation_tracking()
        chunks = retriever.retrieve("exam panic", self._eos())

        assert chunks == self.DOCS, "fallback did not preserve MMR order"
        assert len(chunks) == 3
        assert RERANKER_DEGRADED in sink, "degraded turn was not recorded"

    def test_disabled_setting_skips_the_model_entirely(
        self, mock_store: MagicMock, scoring_manager: MagicMock, monkeypatch
    ) -> None:
        monkeypatch.setattr(settings, "rag_reranker_enabled", False)
        retriever = TherapyRetriever(
            vector_store=mock_store, k=3, fetch_k=10, model_manager=scoring_manager
        )

        sink = begin_degradation_tracking()
        chunks = retriever.retrieve("exam panic", self._eos())

        assert chunks == self.DOCS, "MMR order should be served unchanged"
        scoring_manager.rerank.assert_not_called()
        assert RERANKER_DEGRADED not in sink, "disabling is not a degradation"

