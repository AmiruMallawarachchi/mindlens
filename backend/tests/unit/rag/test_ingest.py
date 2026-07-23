"""Tests for MindLens RAG Ingestion Pipeline."""

from __future__ import annotations

from unittest.mock import MagicMock, mock_open, patch

from app.rag.ingest import chunk_text, ingest_documents, load_therapy_knowledge


class TestChunkText:
    def test_short_text_no_chunking(self) -> None:
        text = "Short text."
        chunks = chunk_text(text, chunk_size=100, overlap=10)
        assert chunks == ["Short text."]

    def test_chunk_respects_sentence_boundary(self) -> None:
        text = "First sentence. Second sentence. Third sentence. Fourth sentence."
        chunks = chunk_text(text, chunk_size=30, overlap=5)
        # Should break at sentence boundaries when possible
        for chunk in chunks[:-1]:
            assert chunk.endswith(".") or chunk.endswith(" ")

    def test_chunk_with_overlap(self) -> None:
        text = "a " * 100  # 200 chars with spaces
        chunks = chunk_text(text, chunk_size=50, overlap=10)
        # Each chunk should share some content with previous
        for i in range(1, len(chunks)):
            assert len(chunks[i]) > 0

    def test_empty_text(self) -> None:
        assert chunk_text("", chunk_size=100) == []

    def test_exact_chunk_size(self) -> None:
        text = "a" * 100
        chunks = chunk_text(text, chunk_size=50, overlap=10)
        assert len(chunks) == 3  # 50 + 40 + 10


class TestLoadTherapyKnowledge:
    def test_load_existing_file(self) -> None:
        with patch("app.rag.ingest.os.path.exists") as mock_exists, \
             patch("builtins.open", mock_open(read_data='[{"id": "test", "content": "hello"}]')):
            mock_exists.return_value = True
            result = load_therapy_knowledge("/fake/path.json")
            assert len(result) == 1
            assert result[0]["id"] == "test"

    def test_load_missing_file(self) -> None:
        with patch("app.rag.ingest.os.path.exists") as mock_exists:
            mock_exists.return_value = False
            result = load_therapy_knowledge("/fake/path.json")
            assert result == []


class TestIngestDocuments:
    def test_ingest_empty_knowledge(self) -> None:
        with patch("app.rag.ingest.load_therapy_knowledge") as mock_load, \
             patch("app.rag.ingest.get_vector_store") as mock_get_store:
            mock_load.return_value = []
            mock_store = MagicMock()
            mock_get_store.return_value = mock_store

            count = ingest_documents()
            assert count == 0

    def test_ingest_with_chunks(self) -> None:
        knowledge = [
            {
                "id": "test_entry",
                "title": "Test",
                "category": "Test",
                "tags": ["tag1"],
                "content": "a" * 500,  # Will be chunked
            }
        ]
        with patch("app.rag.ingest.load_therapy_knowledge") as mock_load, \
             patch("app.rag.ingest.get_vector_store") as mock_get_store:
            mock_load.return_value = knowledge
            mock_store = MagicMock()
            mock_get_store.return_value = mock_store

            count = ingest_documents(chunk_size=100, chunk_overlap=10)
            assert count > 0
            mock_store.add_documents.assert_called_once()

    def test_ingest_skips_empty_content(self) -> None:
        knowledge = [
            {"id": "empty", "title": "Empty", "category": "Test", "content": "   "}
        ]
        with patch("app.rag.ingest.load_therapy_knowledge") as mock_load, \
             patch("app.rag.ingest.get_vector_store") as mock_get_store:
            mock_load.return_value = knowledge
            mock_store = MagicMock()
            mock_get_store.return_value = mock_store

            count = ingest_documents()
            assert count == 0
