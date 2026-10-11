"""Pinecone hosted retrieval for MindLens V2."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class HostedRetriever:
    def __init__(self) -> None:
        from pinecone import Pinecone

        if not settings.pinecone_api_key or not settings.pinecone_index_name:
            raise RuntimeError("Pinecone is not configured")
        self.client = Pinecone(api_key=settings.pinecone_api_key)
        self.index = self.client.Index(settings.pinecone_index_name)

    def _embed(self, text: str, input_type: str) -> list[float]:
        result = self.client.inference.embed(
            model=settings.pinecone_embedding_model,
            inputs=[text],
            parameters={"input_type": input_type, "truncate": "END"},
        )
        item = result[0] if hasattr(result, "__getitem__") else next(iter(result))
        return list(item.values)

    def retrieve(self, text: str) -> list[str]:
        # Integrated Pinecone indexes can embed and search text entirely on
        # the hosted service. This is the preferred path for V2.
        try:
            result = self.index.search(
                namespace="therapy",
                query={"inputs": {"text": text}, "top_k": settings.pinecone_top_k},
            )
            hits = result.get("result", {}).get("hits", []) if isinstance(result, dict) else []
            return [str(hit.get("fields", {}).get("text")) for hit in hits if hit.get("fields", {}).get("text")]
        except Exception:
            pass
        vector = self._embed(text, "query")
        result = self.index.query(vector=vector, top_k=settings.pinecone_top_k, include_metadata=True)
        chunks: list[str] = []
        for match in result.get("matches", []) if isinstance(result, dict) else getattr(result, "matches", []):
            metadata = match.get("metadata", {}) if isinstance(match, dict) else getattr(match, "metadata", {})
            value = metadata.get("text")
            if value:
                chunks.append(str(value))
        return chunks


@lru_cache(maxsize=1)
def get_hosted_retriever() -> HostedRetriever:
    return HostedRetriever()
