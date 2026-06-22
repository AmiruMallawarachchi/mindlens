"""
MindLens RAG Ingestion Pipeline
===============================
Loads curated therapy knowledge from JSON, chunks it,
embeds via all-MiniLM-L6-v2, and stores in ChromaDB.

Usage:
    python -m app.rag.ingest

Or call programmatically:
    from app.rag.ingest import ingest_documents
    ingest_documents()
"""

from __future__ import annotations

import json
import os
from typing import Any

from app.rag.vector_store import get_vector_store
from app.utils.logger import get_logger

logger = get_logger(__name__)

_KNOWLEDGE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "therapy_knowledge.json"
)

# Chunking parameters (approximate: 400 chars / 50 overlap)
_CHUNK_SIZE = 400
_CHUNK_OVERLAP = 50


def load_therapy_knowledge(path: str | None = None) -> list[dict[str, Any]]:
    """
    Load therapy knowledge JSON.

    Expected format:
    [
      {
        "id": "cbt_thought_record",
        "title": "CBT Thought Record",
        "category": "CBT",
        "content": "full text here...",
        "tags": ["cbt", "anxiety", "cognitive"]
      },
      ...
    ]
    """
    path = path or _KNOWLEDGE_PATH
    if not os.path.exists(path):
        logger.warning("Knowledge file not found: %s", path)
        return []

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    logger.info("Loaded %d knowledge entries from %s", len(data), path)
    return data


def chunk_text(text: str, chunk_size: int = _CHUNK_SIZE, overlap: int = _CHUNK_OVERLAP) -> list[str]:
    """
    Recursive character chunking with overlap.

    Splits at sentence boundaries when possible, then word boundaries,
    then hard character boundaries.
    """
    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)

        # Try to break at sentence boundary
        if end < text_len:
            for pos in range(end, start + chunk_size // 2, -1):
                if pos < text_len and text[pos] in ".!?" and pos + 1 < text_len and text[pos + 1] in " \n":
                    end = pos + 1
                    break
            else:
                # Try word boundary
                for pos in range(end, start + chunk_size // 2, -1):
                    if pos < text_len and text[pos] == " ":
                        end = pos
                        break

        chunks.append(text[start:end].strip())
        start = end - overlap if end < text_len else end

    return [c for c in chunks if c]


def ingest_documents(
    knowledge_path: str | None = None,
    chunk_size: int = _CHUNK_SIZE,
    chunk_overlap: int = _CHUNK_OVERLAP,
) -> int:
    """
    Load therapy knowledge, chunk, embed, and store in ChromaDB.

    Returns the number of chunks ingested.
    """
    entries = load_therapy_knowledge(knowledge_path)
    if not entries:
        logger.warning("No knowledge entries to ingest.")
        return 0

    store = get_vector_store()
    store.connect()

    docs: list[str] = []
    ids: list[str] = []
    metadatas: list[dict[str, Any]] = []

    for entry in entries:
        entry_id = entry.get("id", "unknown")
        category = entry.get("category", "general")
        tags = entry.get("tags", [])
        content = entry.get("content", "")
        title = entry.get("title", "")

        if not content.strip():
            continue

        chunks = chunk_text(content, chunk_size=chunk_size, overlap=chunk_overlap)
        for idx, chunk in enumerate(chunks):
            chunk_id = f"{entry_id}_chunk_{idx}"
            docs.append(chunk)
            ids.append(chunk_id)
            metadatas.append(
                {
                    "entry_id": entry_id,
                    "title": title,
                    "category": category,
                    "tags": ", ".join(tags) if isinstance(tags, list) else str(tags),
                    "chunk_index": idx,
                    "total_chunks": len(chunks),
                }
            )

    if docs:
        store.add_documents(documents=docs, ids=ids, metadatas=metadatas)
        logger.info("Ingested %d chunks into ChromaDB", len(docs))
    else:
        logger.warning("No chunks generated from knowledge entries.")

    return len(docs)


if __name__ == "__main__":
    count = ingest_documents()
    print(f"Ingested {count} chunks into ChromaDB.")
