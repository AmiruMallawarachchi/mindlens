"""Idempotently publish the curated therapy corpus to Pinecone.

Run from the repository root after creating a Pinecone Starter index:
    python scripts/ingest_pinecone.py

The script sends only the curated corpus. User messages and memories never
enter this index.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pinecone import Pinecone


def chunk_text(text: str, size: int = 400, overlap: int = 50) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            boundary = text.rfind(". ", start + size // 3, end)
            if boundary > start:
                end = boundary + 1
        chunks.append(text[start:end].strip())
        start = end - overlap if end < len(text) else end
    return [chunk for chunk in chunks if chunk]


def main() -> None:
    api_key = os.environ["PINECONE_API_KEY"]
    index_name = os.environ["PINECONE_INDEX_NAME"]
    path = Path(os.getenv("RAG_KNOWLEDGE_PATH", "backend/data/therapy_knowledge.json"))
    client = Pinecone(api_key=api_key)
    index = client.Index(index_name)
    entries: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    records: list[dict[str, Any]] = []
    for entry in entries:
        content = str(entry.get("content", "")).strip()
        chunks = chunk_text(content)
        for number, text in enumerate(chunks):
            records.append(
                {
                    "id": f"{entry.get('id', 'entry')}_chunk_{number}",
                    "text": text,
                    "entry_id": entry.get("id", ""),
                    "title": entry.get("title", ""),
                    "category": entry.get("category", "general"),
                    "tags": ", ".join(entry.get("tags", [])),
                    "source_url": entry.get("source_url", ""),
                }
            )
    for offset in range(0, len(records), 50):
        index.upsert_records("therapy", records[offset : offset + 50])
    print(f"Upserted {len(records)} hosted therapy records into {index_name}.")


if __name__ == "__main__":
    main()
