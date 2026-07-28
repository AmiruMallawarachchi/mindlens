"""Tests for MindLens RAG Therapy Retriever."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from app.core.emotional_os import EmotionalOperatingState, Modality
from app.rag.retriever import TherapyRetriever, get_retriever


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
    def retriever(self, mock_store):
        return TherapyRetriever(vector_store=mock_store, k=2, fetch_k=10, lambda_mult=0.5)

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


class TestSingleton:
    def test_get_retriever_returns_singleton(self) -> None:
        with patch("app.rag.retriever.get_vector_store"):
            r1 = get_retriever()
            r2 = get_retriever()
            assert r1 is r2
