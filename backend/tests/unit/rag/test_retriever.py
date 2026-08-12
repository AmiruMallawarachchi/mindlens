"""Tests for MindLens RAG Therapy Retriever."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from app.agents.groq_client import begin_degradation_tracking
from app.config import settings
from app.core.emotional_os import EmotionalOperatingState, Modality
from app.rag.retriever import RERANKER_DEGRADED, TherapyRetriever, get_retriever


class TestTherapyRetriever:
    """Unit tests for TherapyRetriever."""

    @pytest.fixture
    def mock_store(self):
        store = MagicMock()
        store.connect = MagicMock()
        store.query_mmr.return_value = {
            "documents": [["CBT technique for anxiety", "Mindfulness for stress"]],
            "metadatas": [[
                {"category": "CBT", "tags": "cbt, anxiety", "title": "CBT"},
                {"category": "Mindfulness", "tags": "mindfulness, stress", "title": "Mindfulness"},
            ]],
            "ids": [["id1", "id2"]],
            "distances": [[0.1, 0.2]],
        }
        return store

    @pytest.fixture
    def mock_manager(self):
        """A ModelManager whose reranker scores every pair identically.

        Injected so these tests never reach the real cross-encoder — without
        it the retriever lazily loads the published model over the network.
        """
        manager = MagicMock()
        manager.rerank.side_effect = lambda query, docs: [0.5] * len(docs)
        return manager

    @pytest.fixture
    def retriever(self, mock_store, mock_manager):
        return TherapyRetriever(
            vector_store=mock_store,
            k=2,
            fetch_k=10,
            lambda_mult=0.5,
            model_manager=mock_manager,
        )

    def test_retrieve_returns_chunks(self, retriever: TherapyRetriever, mock_store: MagicMock) -> None:
        eos = EmotionalOperatingState(
            surface_emotion="anxiety",
            modality=Modality.CBT,
            age_group="adult",
        )
        chunks = retriever.retrieve("I feel anxious about my exam", eos)
        assert len(chunks) > 0
        mock_store.connect.assert_called_once()
        mock_store.query_mmr.assert_called_once()

    def test_retrieve_with_metadata(self, retriever: TherapyRetriever, mock_store: MagicMock) -> None:
        eos = EmotionalOperatingState(
            surface_emotion="stress",
            modality=Modality.DBT,
            age_group="teen",
        )
        results = retriever.retrieve_with_metadata("Feeling stressed", eos)
        assert len(results) > 0
        assert "text" in results[0]
        assert "category" in results[0]
        assert "score" in results[0]

    def test_build_query(self, retriever: TherapyRetriever) -> None:
        eos = EmotionalOperatingState(
            surface_emotion="anxiety",
            modality=Modality.CBT,
            age_group="adult",
        )
        query = retriever._build_query("I feel anxious", eos)
        assert "anxiety" in query
        assert "CBT" in query
        assert "I feel anxious" in query

    def test_build_query_with_distortion(self, retriever: TherapyRetriever) -> None:
        eos = EmotionalOperatingState(
            surface_emotion="depression",
            modality=Modality.CBT,
            age_group="adult",
        )
        # Set distortion_label manually
        eos.distortion_label = "catastrophizing"
        query = retriever._build_query("Everything is going wrong", eos)
        assert "catastrophizing" in query

    def test_rerank_by_age_group_teen(self, retriever: TherapyRetriever) -> None:
        docs = ["School stress help", "Work stress help", "Peer pressure tips"]
        metas = [
            {"tags": "teen, school, exam", "category": "Self-Care"},
            {"tags": "adult, work, career", "category": "Self-Care"},
            {"tags": "teen, peer, school", "category": "Self-Care"},
        ]
        ranked = retriever._rerank_by_age_group(docs, metas, age_group="teen")
        # Teen-related docs should be first
        assert "School" in ranked[0] or "Peer" in ranked[0]

    def test_rerank_by_age_group_adult(self, retriever: TherapyRetriever) -> None:
        docs = ["School stress help", "Work stress help", "Peer pressure tips"]
        metas = [
            {"tags": "teen, school, exam", "category": "Self-Care"},
            {"tags": "adult, work, career", "category": "Self-Care"},
            {"tags": "teen, peer, school", "category": "Self-Care"},
        ]
        ranked = retriever._rerank_by_age_group(docs, metas, age_group="adult")
        # Adult-related docs should be first
        assert "Work" in ranked[0]

    def test_rerank_no_age_group(self, retriever: TherapyRetriever) -> None:
        docs = ["doc1", "doc2"]
        metas = [{"tags": "a", "category": "A"}, {"tags": "b", "category": "B"}]
        ranked = retriever._rerank_by_age_group(docs, metas, age_group=None)
        assert ranked == docs  # No change

    def test_retrieve_graceful_failure(self, retriever: TherapyRetriever, mock_store: MagicMock) -> None:
        mock_store.query_mmr.side_effect = RuntimeError("ChromaDB error")
        eos = EmotionalOperatingState(
            surface_emotion="anxiety",
            modality=Modality.CBT,
            age_group="adult",
        )
        chunks = retriever.retrieve("test", eos)
        assert chunks == []  # Graceful fallback

    def test_retrieve_with_metadata_graceful_failure(self, retriever: TherapyRetriever, mock_store: MagicMock) -> None:
        mock_store.query_mmr.side_effect = RuntimeError("ChromaDB error")
        eos = EmotionalOperatingState(
            surface_emotion="anxiety",
            modality=Modality.CBT,
            age_group="adult",
        )
        results = retriever.retrieve_with_metadata("test", eos)
        assert results == []  # Graceful fallback


class TestCrossEncoderReranking:
    """T1 — the fine-tuned cross-encoder actually orders retrieval."""

    #: MMR hands these back in this order; the reranker disagrees.
    DOCS = ["mmr first", "mmr second", "mmr third"]
    #: Scores keyed by document — "mmr third" is the genuinely relevant one.
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
        boundary — see tests/unit/models/test_loader.py.
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

class TestAgeGroupBoost:
    """The age heuristic is a bounded additive boost, not a dead tie-breaker."""

    @pytest.fixture
    def mock_store(self):
        store = MagicMock()
        store.connect = MagicMock()
        store.query_mmr.return_value = {
            "documents": [["generic", "teen tagged"]],
            "metadatas": [[
                {"category": "CBT", "tags": ""},
                {"category": "CBT", "tags": "teen, school"},
            ]],
            "ids": [["id1", "id2"]],
            "distances": [[0.1, 0.2]],
        }
        return store

    @staticmethod
    def _eos() -> EmotionalOperatingState:
        return EmotionalOperatingState(
            surface_emotion="anxiety", modality=Modality.CBT, age_group="teen"
        )

    @staticmethod
    def _retriever(store, scores: dict[str, float]) -> TherapyRetriever:
        manager = MagicMock()
        manager.rerank.side_effect = lambda query, docs: [scores[d] for d in docs]
        return TherapyRetriever(
            vector_store=store, k=2, fetch_k=10, model_manager=manager
        )

    def test_boost_flips_a_close_call(self, mock_store: MagicMock, monkeypatch) -> None:
        """A 0.02 relevance gap is inside a 0.05 boost, so the match wins."""
        monkeypatch.setattr(settings, "rag_age_boost", 0.05)
        retriever = self._retriever(
            mock_store, {"generic": 0.52, "teen tagged": 0.50}
        )
        assert retriever.retrieve("x", self._eos()) == ["teen tagged", "generic"]

    def test_boost_never_overturns_a_decisive_relevance_gap(
        self, mock_store: MagicMock, monkeypatch
    ) -> None:
        """Bounded: 0.8 of relevance is not undone by a 0.05 boost."""
        monkeypatch.setattr(settings, "rag_age_boost", 0.05)
        retriever = self._retriever(
            mock_store, {"generic": 0.9, "teen tagged": 0.1}
        )
        assert retriever.retrieve("x", self._eos()) == ["generic", "teen tagged"]

    def test_zero_boost_leaves_ranking_to_the_model_alone(
        self, mock_store: MagicMock, monkeypatch
    ) -> None:
        """The T7c null case — if the sweep says the heuristic hurts, this ships."""
        monkeypatch.setattr(settings, "rag_age_boost", 0.0)
        retriever = self._retriever(
            mock_store, {"generic": 0.52, "teen tagged": 0.50}
        )
        assert retriever.retrieve("x", self._eos()) == ["generic", "teen tagged"]

    def test_boost_is_the_only_signal_when_the_model_is_unavailable(
        self, mock_store: MagicMock, monkeypatch
    ) -> None:
        """Fallback keeps the pre-reranker behaviour rather than losing it."""
        monkeypatch.setattr(settings, "rag_age_boost", 0.05)
        manager = MagicMock()
        manager.rerank.side_effect = RuntimeError("model unavailable")
        retriever = TherapyRetriever(
            vector_store=mock_store, k=2, fetch_k=10, model_manager=manager
        )
        assert retriever.retrieve("x", self._eos()) == ["teen tagged", "generic"]


class TestSingleton:
    def test_get_retriever_returns_singleton(self) -> None:
        with patch("app.rag.retriever.get_vector_store"):
            r1 = get_retriever()
            r2 = get_retriever()
            assert r1 is r2
