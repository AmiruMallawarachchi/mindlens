"""Age-group relevance boost coverage for the local therapy retriever."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from app.config import settings
from app.core.emotional_os import EmotionalOperatingState, Modality
from app.rag.retriever import TherapyRetriever
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
        """The T7c null case â€” if the sweep says the heuristic hurts, this ships."""
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

