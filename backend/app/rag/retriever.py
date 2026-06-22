"""
MindLens Therapy Retriever
===========================
MMR-based retriever for therapy knowledge.

- Builds retrieval query from EOS state
- MMR search with diversity-relevance tradeoff
- Re-ranks by user age group (teen vs adult content)
- Returns top-k chunks as strings for prompt injection

Usage:
    retriever = get_retriever()
    chunks = retriever.retrieve("anxiety about exams", eos, k=5)
"""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.core.emotional_os import EmotionalOperatingState
from app.rag.vector_store import TherapyVectorStore, get_vector_store
from app.utils.logger import get_logger

logger = get_logger(__name__)

_DEFAULT_K = 5
_DEFAULT_FETCH_K = 20
_DEFAULT_LAMBDA = 0.5


class TherapyRetriever:
    """
    Retrieves relevant therapy knowledge chunks for a given user query + EOS.
    """

    def __init__(
        self,
        vector_store: TherapyVectorStore | None = None,
        k: int = _DEFAULT_K,
        fetch_k: int = _DEFAULT_FETCH_K,
        lambda_mult: float = _DEFAULT_LAMBDA,
    ) -> None:
        self.store = vector_store or get_vector_store()
        self.k = k
        self.fetch_k = fetch_k
        self.lambda_mult = lambda_mult

    # -----------------------------------------------------------------------
    # Core retrieval
    # -----------------------------------------------------------------------

    def retrieve(
        self,
        user_text: str,
        eos: EmotionalOperatingState,
        k: int | None = None,
    ) -> list[str]:
        """
        Retrieve the top-k relevant therapy knowledge chunks.

        Args:
            user_text: Anonymized user message
            eos: Current emotional operating state
            k: Override default top-k

        Returns:
            List of chunk strings, ordered by relevance
        """
        query = self._build_query(user_text, eos)
        top_k = k or self.k

        try:
            self.store.connect()
            results = self.store.query_mmr(
                query_texts=[query],
                n_results=top_k,
                fetch_k=self.fetch_k,
                lambda_mult=self.lambda_mult,
            )
        except Exception as exc:
            logger.warning("RAG retrieval failed: %s", exc)
            return []

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0] or []

        # Re-rank by age group relevance (boost teen/adult specific content)
        ranked = self._rerank_by_age_group(
            documents, metadatas, age_group=eos.age_group
        )

        logger.info(
            "RAG retrieved %d chunks for query '%s'", len(ranked), query[:60]
        )
        return ranked

    def retrieve_with_metadata(
        self,
        user_text: str,
        eos: EmotionalOperatingState,
        k: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve chunks with full metadata (for debugging / transparency).

        Returns list of dicts: {id, text, category, title, tags, score}.
        """
        query = self._build_query(user_text, eos)
        top_k = k or self.k

        try:
            self.store.connect()
            results = self.store.query_mmr(
                query_texts=[query],
                n_results=top_k,
                fetch_k=self.fetch_k,
                lambda_mult=self.lambda_mult,
            )
        except Exception as exc:
            logger.warning("RAG retrieval failed: %s", exc)
            return []

        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0] or []
        ids = results.get("ids", [[]])[0]
        distances = results.get("distances", [[]])[0]

        ranked = self._rerank_by_age_group(
            docs, metas, age_group=eos.age_group
        )

        # Rebuild metadata list in same order as ranked docs
        ranked_set = {d for d in ranked}
        output = []
        for doc, meta, doc_id, dist in zip(docs, metas, ids, distances):
            if doc in ranked_set:
                output.append(
                    {
                        "id": doc_id,
                        "text": doc,
                        "category": meta.get("category", "general"),
                        "title": meta.get("title", ""),
                        "tags": meta.get("tags", ""),
                        "score": 1.0 - float(dist),
                    }
                )

        # Reorder to match ranked
        output_ordered = []
        for doc in ranked:
            for item in output:
                if item["text"] == doc:
                    output_ordered.append(item)
                    break

        return output_ordered[:top_k]

    # -----------------------------------------------------------------------
    # Query construction
    # -----------------------------------------------------------------------

    @staticmethod
    def _build_query(user_text: str, eos: EmotionalOperatingState) -> str:
        """
        Build a retrieval query that combines emotion, modality, and user text.

        Per SYSTEM.md §10: "Retrieval query = f'{surface_emotion} {modality} {distortion_label}'"
        """
        parts = [
            eos.surface_emotion,
            eos.modality.value if eos.modality else "",
        ]
        if hasattr(eos, "distortion_label") and eos.distortion_label:
            parts.append(eos.distortion_label)

        # Add user text keywords (first 30 words) for grounding
        words = user_text.split()[:30]
        text_summary = " ".join(words)

        query = " ".join(p for p in parts if p)
        if text_summary:
            query += f" {text_summary}"
        return query.strip()

    # -----------------------------------------------------------------------
    # Re-ranking
    # -----------------------------------------------------------------------

    def _rerank_by_age_group(
        self,
        documents: list[str],
        metadatas: list[dict[str, Any]],
        age_group: str | None,
    ) -> list[str]:
        """
        Boost documents whose tags or category match the age group.

        Teen: boost entries tagged 'teen', 'adolescent', 'school', 'exam'
        Adult: boost entries tagged 'adult', 'work', 'career', 'relationship'
        """
        if not age_group:
            return documents

        boost_keywords = {
            "teen": ["teen", "adolescent", "school", "exam", "peer", "parent"],
            "adult": ["adult", "work", "career", "relationship", "partner", "colleague"],
        }

        keywords = boost_keywords.get(age_group.lower(), [])
        if not keywords:
            return documents

        scored = []
        for doc, meta in zip(documents, metadatas):
            tags = meta.get("tags", "")
            category = meta.get("category", "")
            text = f"{tags} {category}".lower()
            score = sum(1 for kw in keywords if kw in text)
            scored.append((score, doc))

        # Sort by score descending, then keep original order for ties
        scored.sort(key=lambda x: (-x[0], documents.index(x[1])))
        return [doc for _, doc in scored]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_retriever: TherapyRetriever | None = None


def get_retriever() -> TherapyRetriever:
    """Return the global TherapyRetriever singleton."""
    global _retriever
    if _retriever is None:
        _retriever = TherapyRetriever()
    return _retriever
