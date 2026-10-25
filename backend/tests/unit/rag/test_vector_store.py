"""Compatibility checks for the removed V1 local Chroma vector store."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from app.rag import vector_store
from app.rag.vector_store import TherapyVectorStore, get_vector_store


def test_local_chroma_connect_reports_v2_removal(monkeypatch: pytest.MonkeyPatch) -> None:
    """V2 uses Pinecone; local Chroma setup must fail with a clear message."""
    monkeypatch.setattr(vector_store, "chromadb", None)
    monkeypatch.setattr(vector_store, "embedding_functions", None)
    monkeypatch.setattr(vector_store, "ChromaSettings", None)

    store = TherapyVectorStore(
        persist_directory="/tmp/test_chroma",
        collection_name="test_collection",
    )

    with pytest.raises(RuntimeError, match="Local ChromaDB was removed in MindLens V2; use Pinecone"):
        store.connect()


def test_get_vector_store_returns_singleton() -> None:
    with patch("app.rag.vector_store.chromadb"):
        with patch("app.rag.vector_store.embedding_functions"):
            first = get_vector_store()
            second = get_vector_store()
            assert first is second
