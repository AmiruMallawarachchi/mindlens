"""Tests for MindLens RAG Vector Store."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from app.rag.vector_store import TherapyVectorStore, get_vector_store


class TestTherapyVectorStore:
    """Unit tests for TherapyVectorStore (mocked ChromaDB)."""

    @pytest.fixture
    def store(self):
        with patch("app.rag.vector_store.chromadb") as mock_chroma, \
             patch("app.rag.vector_store.embedding_functions"):
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_collection.count.return_value = 0
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_chroma.PersistentClient.return_value = mock_client
            store = TherapyVectorStore(
                persist_directory="/tmp/test_chroma",
                collection_name="test_collection",
            )
            store.connect()
            yield store

    def test_connect_initializes_client(self, store: TherapyVectorStore) -> None:
        assert store._client is not None
        assert store._collection is not None

    def test_add_documents(self, store: TherapyVectorStore) -> None:
        store.add_documents(
            documents=["doc1", "doc2"],
            ids=["id1", "id2"],
            metadatas=[{"a": 1}, {"b": 2}],
        )
        store._collection.upsert.assert_called_once_with(
            documents=["doc1", "doc2"],
            ids=["id1", "id2"],
            metadatas=[{"a": 1}, {"b": 2}],
        )

    def test_delete_documents(self, store: TherapyVectorStore) -> None:
        store.delete_documents(["id1", "id2"])
        store._collection.delete.assert_called_once_with(ids=["id1", "id2"])

    def test_query(self, store: TherapyVectorStore) -> None:
        store._collection.query.return_value = {
            "ids": [["id1"]],
            "distances": [[0.1]],
            "documents": [["doc1"]],
            "metadatas": [[{"a": 1}]],
        }
        result = store.query(["test query"], n_results=5)
        assert result["ids"][0][0] == "id1"
        assert result["documents"][0][0] == "doc1"

    def test_count(self, store: TherapyVectorStore) -> None:
        store._collection.count.return_value = 42
        assert store.count() == 42

    def test_peek(self, store: TherapyVectorStore) -> None:
        store._collection.peek.return_value = {"ids": [["id1"]]}
        result = store.peek(limit=1)
        assert result["ids"][0][0] == "id1"

    def test_mmr_rerank(self, store: TherapyVectorStore) -> None:
        results = {
            "documents": [["a", "b", "c"]],
            "ids": [["id_a", "id_b", "id_c"]],
            "distances": [[0.1, 0.2, 0.3]],
            "metadatas": [[{}, {}, {}]],
            "embeddings": [[[1.0, 0.0], [0.9, 0.1], [0.0, 1.0]]],
        }
        mmr = store._mmr_rerank(results, results["embeddings"][0], n_results=2, lambda_mult=0.5)
        assert len(mmr["documents"][0]) == 2
        assert mmr["ids"][0][0] == "id_a"  # Most relevant

    def test_mmr_rerank_with_numpy_embeddings(self, store: TherapyVectorStore) -> None:
        """Regression — chromadb's real `collection.query(..., include=[...,
        "embeddings"])` returns `embeddings` as a numpy.ndarray, not the
        plain nested list the other tests here use as a fixture.
        `not embeddings` on a multi-row ndarray raises ValueError ("truth
        value of an array... is ambiguous") instead of testing emptiness —
        this went unnoticed because the vector store was empty in every
        environment until RAG's cwd-relative path bug was fixed, so no real
        query had ever reached this line with actual data."""
        results = {
            "documents": [["a", "b", "c"]],
            "ids": [["id_a", "id_b", "id_c"]],
            "distances": [[0.1, 0.2, 0.3]],
            "metadatas": [[{}, {}, {}]],
            "embeddings": [np.array([[1.0, 0.0], [0.9, 0.1], [0.0, 1.0]])],
        }
        mmr = store._mmr_rerank(results, results["embeddings"][0], n_results=2, lambda_mult=0.5)
        assert len(mmr["documents"][0]) == 2
        assert mmr["ids"][0][0] == "id_a"

    def test_mmr_rerank_empty_embeddings_returns_results_unchanged(
        self, store: TherapyVectorStore
    ) -> None:
        results = {
            "documents": [[]],
            "ids": [[]],
            "distances": [[]],
            "metadatas": [[]],
            "embeddings": [np.array([])],
        }
        mmr = store._mmr_rerank(results, results["embeddings"][0], n_results=2, lambda_mult=0.5)
        assert mmr is results

    def test_cosine_sim_identical(self, store: TherapyVectorStore) -> None:
        a = [1.0, 0.0, 0.0]
        assert store._cosine_sim(a, a) == pytest.approx(1.0)

    def test_cosine_sim_orthogonal(self, store: TherapyVectorStore) -> None:
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert store._cosine_sim(a, b) == pytest.approx(0.0)

    def test_cosine_sim_zero_vector(self, store: TherapyVectorStore) -> None:
        a = [0.0, 0.0]
        b = [1.0, 0.0]
        assert store._cosine_sim(a, b) == 0.0


class TestSingleton:
    def test_get_vector_store_returns_singleton(self) -> None:
        with patch("app.rag.vector_store.chromadb"):
            with patch("app.rag.vector_store.embedding_functions"):
                s1 = get_vector_store()
                s2 = get_vector_store()
                assert s1 is s2
