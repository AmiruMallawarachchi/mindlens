"""Pinecone hosted retrieval for MindLens V2."""

from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Any

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

PROBE_TIMEOUT_SECONDS = 5

# Where the curated corpus lives inside the index. `scripts/ingest_pinecone.py`
# writes this same literal, and Pinecone silently searches an empty default
# namespace when a query omits it — so both sides name it explicitly.
NAMESPACE = "therapy"


def _classify_probe_error(exc: Exception) -> tuple[str, str]:
    code = getattr(exc, "status", None) or getattr(
        getattr(exc, "response", None), "status_code", None
    )
    try:
        code = int(code)
    except (TypeError, ValueError):
        code = None
    if code in (401, 403):
        return "unauthorized", "the API key was rejected"
    if code == 404:
        return "index_not_found", f"no index named {settings.pinecone_index_name}"
    return "unreachable", str(exc)[:160]


def probe_rag() -> dict[str, Any]:
    """Ask Pinecone, rather than the config, whether retrieval is usable.

    A key sitting in the environment proves nothing; reporting string presence
    as "configured" told operators that RAG was fine while every query failed.
    """
    if not settings.pinecone_api_key or not settings.pinecone_index_name:
        return {"provider": "pinecone", "status": "not_configured"}

    from pinecone import Pinecone

    try:
        description = Pinecone(api_key=settings.pinecone_api_key).describe_index(
            settings.pinecone_index_name
        )
    except Exception as exc:  # noqa: BLE001 - any failure means "not reachable"
        status, detail = _classify_probe_error(exc)
        logger.warning("Pinecone probe failed (%s): %s", status, detail)
        return {"provider": "pinecone", "status": status, "detail": detail}

    dimension = getattr(description, "dimension", None)
    return {
        "provider": "pinecone",
        "status": "reachable",
        "index": settings.pinecone_index_name,
        "dimension": dimension,
    }


async def rag_status() -> dict[str, Any]:
    """The probe, off the event loop and never longer than the request."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(probe_rag), timeout=PROBE_TIMEOUT_SECONDS
        )
    except TimeoutError:
        return {
            "provider": "pinecone",
            "status": "unreachable",
            "detail": f"no response within {PROBE_TIMEOUT_SECONDS}s",
        }


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
        # the hosted service, so that is tried first. It is not trusted on an
        # empty answer: this index's `search` returns no hits at all — it
        # succeeds with `hits: []` rather than raising — so falling through
        # only on an exception meant the path that does work was never
        # reached, and every turn retrieved nothing while the probe happily
        # reported the index as reachable.
        try:
            result = self.index.search(
                namespace=NAMESPACE,
                query={"inputs": {"text": text}, "top_k": settings.pinecone_top_k},
            )
            hits = result.get("result", {}).get("hits", []) if isinstance(result, dict) else []
            passages = [
                str(hit.get("fields", {}).get("text"))
                for hit in hits
                if hit.get("fields", {}).get("text")
            ]
            if passages:
                return passages
        except Exception as exc:  # noqa: BLE001 - empty is the signal, not the error
            logger.debug("Integrated Pinecone search failed; querying by vector", exc_info=exc)

        # Hosted inference embeds the query, then a plain vector search reads
        # the records `scripts/ingest_pinecone.py` wrote — into NAMESPACE,
        # which this call must pass explicitly: without it Pinecone searches
        # the default namespace, which is empty, and returns zero matches as
        # a success.
        vector = self._embed(text, "query")
        result = self.index.query(
            vector=vector,
            top_k=settings.pinecone_top_k,
            include_metadata=True,
            namespace=NAMESPACE,
        )
        chunks: list[str] = []
        for match in _matches(result):
            value = _metadata(match).get("text")
            if value:
                chunks.append(str(value))
        return chunks


def _matches(result: Any) -> list[Any]:
    if isinstance(result, dict):
        return list(result.get("matches", []))
    return list(getattr(result, "matches", []) or [])


def _metadata(match: Any) -> dict[str, Any]:
    if isinstance(match, dict):
        return dict(match.get("metadata", {}) or {})
    return dict(getattr(match, "metadata", {}) or {})


@lru_cache(maxsize=1)
def get_hosted_retriever() -> HostedRetriever:
    return HostedRetriever()
