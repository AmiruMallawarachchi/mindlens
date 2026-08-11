"""
MindLens RAG Vector Store
==========================
Thin wrapper around ChromaDB (embedded, in-memory or persisted).

Features:
  - Embedded ChromaDB (no external service)
  - Collection "mindlens_therapy_knowledge"
  - all-MiniLM-L6-v2 embeddings (384-dim)
  - Optional persistence to disk
  - Upsert with idempotency (id-based dedup)
"""

from __future__ import annotations

import os
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.utils import embedding_functions

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

_DEFAULT_COLLECTION = "mindlens_therapy_knowledge"
_DEFAULT_EMBED_MODEL = "all-MiniLM-L6-v2"


class TherapyVectorStore:
    """
    Manages the ChromaDB client, collection, and basic CRUD operations.
    """

    def __init__(
        self,
        persist_directory: str | None = None,
        collection_name: str = _DEFAULT_COLLECTION,
        embedding_model: str = _DEFAULT_EMBED_MODEL,
    ) -> None:
        self.collection_name = collection_name
        self.embedding_model = embedding_model
        self.persist_directory = persist_directory or os.path.join(
            os.path.dirname(__file__), "..", "..", "chroma_db"
        )
        os.makedirs(self.persist_directory, exist_ok=True)

        self._client: chromadb.Client | None = None
        self._collection: chromadb.Collection | None = None
        self._embedding_function = None

    # -----------------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------------

    def connect(self) -> None:
        """Initialize ChromaDB client and get/create collection."""
        if self._client is not None:
            return

        self._embedding_function = (
            embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=self.embedding_model
            )
        )
        self._client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self._embedding_function,
            # hnsw:search_ef defaults low enough (well under 20) that
            # query_mmr's fetch_k=20 request on this small a corpus (67
            # chunks) intermittently failed with hnswlib's "Cannot return
            # the results in a contiguous 2D array. Probably ef or M is too
            # small" -- the index just couldn't guarantee that many
            # candidates at the default search width. 100 comfortably
            # covers fetch_k with room to grow; hnsw:construction_ef raised
            # to match for graph quality, both cheap at this corpus size.
            metadata={
                "hnsw:space": "cosine",
                "hnsw:search_ef": 100,
                "hnsw:construction_ef": 100,
            },
        )
        logger.info(
            "ChromaDB connected: collection=%s count=%d",
            self.collection_name,
            self._collection.count(),
        )

    def disconnect(self) -> None:
        """Close client."""
        if self._client is not None:
            self._client = None
            self._collection = None
            self._embedding_function = None
            logger.info("ChromaDB disconnected.")

    # -----------------------------------------------------------------------
    # CRUD
    # -----------------------------------------------------------------------

    def add_documents(
        self,
        documents: list[str],
        ids: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        """Add or upsert documents into the collection."""
        collection = self._connected_collection()
        collection.upsert(
            documents=documents,
            ids=ids,
            metadatas=metadatas,
        )
        logger.info("Upserted %d documents into ChromaDB", len(documents))

    def delete_documents(self, ids: list[str]) -> None:
        """Delete documents by ID."""
        collection = self._connected_collection()
        collection.delete(ids=ids)
        logger.info("Deleted %d documents from ChromaDB", len(ids))

    def query(
        self,
        query_texts: list[str],
        n_results: int = 5,
        where: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Basic similarity search.
        Returns raw ChromaDB result dict: {ids, distances, documents, metadatas}.
        """
        collection = self._connected_collection()
        return collection.query(
            query_texts=query_texts,
            n_results=n_results,
            where=where,
        )

    def query_mmr(
        self,
        query_texts: list[str],
        n_results: int = 5,
        fetch_k: int = 20,
        lambda_mult: float = 0.5,
        where: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Maximum Marginal Relevance (MMR) search.

        Balances relevance with diversity. First fetches `fetch_k` most similar,
        then greedily selects `n_results` that maximize:
          lambda * relevance - (1 - lambda) * max_similarity_to_already_selected
        """
        collection = self._connected_collection()

        # Fetch top-k by similarity
        results = collection.query(
            query_texts=query_texts,
            n_results=fetch_k,
            where=where,
            include=["documents", "metadatas", "distances", "embeddings"],
        )

        # MMR re-ranking
        mmr_results = self._mmr_rerank(
            results=results,
            query_embeddings=results.get("embeddings", []),
            n_results=n_results,
            lambda_mult=lambda_mult,
        )
        return mmr_results

    def count(self) -> int:
        return self._connected_collection().count()

    def peek(self, limit: int = 5) -> dict[str, Any]:
        return self._connected_collection().peek(limit=limit)

    # -----------------------------------------------------------------------
    # MMR helper
    # -----------------------------------------------------------------------

    def _mmr_rerank(
        self,
        results: dict[str, Any],
        query_embeddings: list,
        n_results: int,
        lambda_mult: float,
    ) -> dict[str, Any]:
        """Greedy MMR re-ranking over a single query."""
        # Simplified MMR: for each query position, greedily select
        docs = results.get("documents", [[]])[0]
        ids = results.get("ids", [[]])[0]
        distances = results.get("distances", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0] or []
        embeddings = results.get("embeddings", [[]])[0]

        # `embeddings` is a numpy.ndarray (chromadb returns query results
        # this way), not a plain list — `not embeddings` on a multi-row array
        # raises "truth value of an array... is ambiguous" rather than
        # testing emptiness. This was never exercised until the vector store
        # actually held data (see ingest.py's cwd-relative path fix): every
        # real query hit this line and silently returned zero chunks via
        # retriever.py's broad except.
        if len(docs) == 0 or len(embeddings) == 0:
            return results

        # Convert distances to relevance scores (lower distance = higher relevance)
        relevance = [1.0 - d for d in distances]

        selected_indices = []
        remaining = set(range(len(docs)))

        for _ in range(min(n_results, len(docs))):
            best_score = -float("inf")
            best_idx = None

            for idx in remaining:
                score = lambda_mult * relevance[idx]
                # Penalize similarity to already selected
                for sel_idx in selected_indices:
                    sim = self._cosine_sim(embeddings[idx], embeddings[sel_idx])
                    score -= (1 - lambda_mult) * sim
                if score > best_score:
                    best_score = score
                    best_idx = idx

            if best_idx is not None:
                selected_indices.append(best_idx)
                remaining.remove(best_idx)

        return {
            "ids": [[ids[i] for i in selected_indices]],
            "distances": [[distances[i] for i in selected_indices]],
            "documents": [[docs[i] for i in selected_indices]],
            "metadatas": [[metadatas[i] for i in selected_indices]] if metadatas else [[]],
        }

    @staticmethod
    def _cosine_sim(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        dot = sum(x * y for x, y in zip(a, b, strict=False))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    # -----------------------------------------------------------------------
    # Internal
    # -----------------------------------------------------------------------

    def _ensure_connected(self) -> None:
        if self._client is None:
            self.connect()

    def _connected_collection(self) -> chromadb.Collection:
        self._ensure_connected()
        if self._collection is None:
            raise RuntimeError("ChromaDB collection failed to initialize")
        return self._collection


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_vector_store: TherapyVectorStore | None = None


def get_vector_store() -> TherapyVectorStore:
    """Return the global TherapyVectorStore singleton."""
    global _vector_store
    if _vector_store is None:
        _vector_store = TherapyVectorStore(
            persist_directory=settings.resolved_chromadb_persist_dir,
            collection_name=settings.rag_collection_name,
            embedding_model=settings.rag_embed_model,
        )
    return _vector_store
