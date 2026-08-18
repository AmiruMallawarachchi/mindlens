"""
MindLens Therapy Retriever
===========================
MMR-based retriever for therapy knowledge, with cross-encoder reranking.

Pipeline per query:

1. Build a retrieval query from the EOS state.
2. MMR search over the vector store for ``fetch_k`` candidates — deliberately
   wider than the ``k`` we return, so the reranker has something to choose
   between. Reranking only the final 5 would waste the model.
3. Score every ``(query, chunk)`` pair with the fine-tuned cross-encoder
   (``mindlens-rag-reranker``) and sort by relevance.
4. Break ties by age group, then truncate to ``k``.

The cross-encoder is a single-label regression head (``num_labels=1``), so the
pipeline's sigmoid score *is* the relevance score and higher is better.

Usage:
    retriever = get_retriever()
    chunks = retriever.retrieve("anxiety about exams", eos, k=5)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.config import settings
from app.core.emotional_os import EmotionalOperatingState
from app.rag.vector_store import TherapyVectorStore, get_vector_store
from app.utils.logger import get_logger

if TYPE_CHECKING:
    from app.models.loader import ModelManager

logger = get_logger(__name__)

_DEFAULT_K = 5
_DEFAULT_FETCH_K = 20
_DEFAULT_LAMBDA = 0.5

#: Recorded on the turn's degradation set when the cross-encoder fails, so a
#: turn served on raw MMR order is never mistaken for a reranked one.
# Namespaced "rag:" so the client can tell a reranker fallback apart from
# an LLM one. It shared the flat degradation sink with Groq failures, and
# the frontend classifies anything without a known prefix as an LLM
# fallback -- so a cross-encoder failure rendered as "the language model
# fell back this turn", which was simply untrue.
RERANKER_DEGRADED = "rag:reranker"


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
        model_manager: ModelManager | None = None,
    ) -> None:
        self.store = vector_store or get_vector_store()
        self.k = k
        self.fetch_k = fetch_k
        self.lambda_mult = lambda_mult
        self._model_manager = model_manager

    @property
    def model_manager(self) -> ModelManager:
        """The process-wide ModelManager, imported lazily to avoid a cycle
        (``app.models.loader`` pulls in config, which pulls in the RAG paths)."""
        if self._model_manager is None:
            from app.models.loader import model_manager

            self._model_manager = model_manager
        return self._model_manager

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

        results = self._query(query)
        if results is None:
            return []

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0] or []

        order = self._ranked_indices(query, documents, metadatas, eos.age_group)
        ranked = [documents[i] for i in order][:top_k]

        logger.info(
            "RAG retrieved %d chunks (from %d candidates) for query '%s'",
            len(ranked),
            len(documents),
            query[:60],
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

        results = self._query(query)
        if results is None:
            return []

        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0] or []
        ids = results.get("ids", [[]])[0]
        distances = results.get("distances", [[]])[0]

        # Index-based ordering, shared with retrieve(). The previous version
        # matched documents back to metadata by text equality, which silently
        # mis-paired any two chunks with identical text.
        order = self._ranked_indices(query, docs, metas, eos.age_group)

        output: list[dict[str, Any]] = []
        for i in order[:top_k]:
            meta = metas[i] if i < len(metas) else {}
            output.append(
                {
                    "id": ids[i] if i < len(ids) else "",
                    "text": docs[i],
                    "category": meta.get("category", "general"),
                    "title": meta.get("title", ""),
                    "tags": meta.get("tags", ""),
                    "score": 1.0 - float(distances[i]) if i < len(distances) else 0.0,
                }
            )
        return output

    # -----------------------------------------------------------------------
    # Candidate fetch + ranking
    # -----------------------------------------------------------------------

    def _query(self, query: str) -> dict[str, Any] | None:
        """Fetch ``fetch_k`` MMR candidates. None if the store is unavailable.

        Note this asks for ``fetch_k`` results, not ``k``: the cross-encoder
        needs a wide candidate pool to be worth running at all.
        """
        try:
            self.store.connect()
            return self.store.query_mmr(
                query_texts=[query],
                n_results=self.fetch_k,
                fetch_k=self.fetch_k,
                lambda_mult=self.lambda_mult,
            )
        except Exception as exc:
            logger.warning("RAG retrieval failed: %s", exc)
            return None

    def _ranked_indices(
        self,
        query: str,
        documents: list[str],
        metadatas: list[dict[str, Any]],
        age_group: str | None,
    ) -> list[int]:
        """Order candidate indices best-first.

        Final score is the cross-encoder's sigmoid relevance plus a bounded
        additive boost (``settings.rag_age_boost``) for chunks whose metadata
        matches the user's age group; ties fall back to the original MMR
        position.

        The boost is additive rather than a tie-breaker on purpose. Sorting by
        float relevance first and using the heuristic only to split exact ties
        would mean it effectively never fires — a control that exists but does
        nothing, which is the failure mode CLAUDE.md rule #1 forbids. Being
        additive and bounded, it can reorder genuinely close candidates without
        ever overturning a decisive relevance gap.

        The magnitude is an empirical question, not a defended constant: T7c
        sweeps it and reports the ranking curve.

        When the cross-encoder is disabled or has failed every relevance score
        is 0.0, so the heuristic decides alone — exactly the pre-reranker
        behaviour, preserved as the fallback.
        """
        if not documents:
            return []

        relevance = self._cross_encoder_scores(query, documents)
        boost = settings.rag_age_boost

        def score(i: int) -> float:
            meta = metadatas[i] if i < len(metadatas) else {}
            # A flat boost on match, not one scaled by keyword count — one
            # knob keeps the T7c sweep interpretable.
            matched = self._age_score(meta, age_group) > 0
            return relevance[i] + (boost if matched else 0.0)

        return sorted(range(len(documents)), key=lambda i: (-score(i), i))

    def _cross_encoder_scores(self, query: str, documents: list[str]) -> list[float]:
        """Relevance score per document from the fine-tuned cross-encoder.

        Returns all-zero scores when reranking is disabled or the model fails —
        a reranker fault must never fail a chat turn, it just costs us the
        improved ordering. Failures are recorded on the turn's degradation set.
        """
        if not settings.rag_reranker_enabled:
            logger.debug("Cross-encoder reranking disabled; serving MMR order")
            return [0.0] * len(documents)

        try:
            # ModelManager owns the batched call so the timing lands in the
            # health entry the admin Model drawer reads.
            return self.model_manager.rerank(query, documents)
        except Exception as exc:
            logger.warning(
                "RAG reranking failed (%s); falling back to MMR order", exc
            )
            self._record_degraded()
            return [0.0] * len(documents)

    @staticmethod
    def _record_degraded() -> None:
        """Mark this turn as degraded, if a turn is in progress."""
        try:
            from app.agents.groq_client import _record_degradation

            _record_degradation(RERANKER_DEGRADED)
        except Exception:  # pragma: no cover - degradation is best-effort
            pass

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

    #: Metadata keywords that mark a chunk as written for an age group.
    _AGE_KEYWORDS = {
        "teen": ["teen", "adolescent", "school", "exam", "peer", "parent"],
        "adult": ["adult", "work", "career", "relationship", "partner", "colleague"],
    }

    @classmethod
    def _age_score(cls, meta: dict[str, Any], age_group: str | None) -> int:
        """How well one chunk's metadata matches the age group.

        A metadata heuristic — keyword counting over tags and category — not a
        model. It runs *after* the cross-encoder as a tie-breaker.
        """
        if not age_group:
            return 0
        keywords = cls._AGE_KEYWORDS.get(age_group.lower(), [])
        if not keywords:
            return 0
        text = f"{meta.get('tags', '')} {meta.get('category', '')}".lower()
        return sum(1 for kw in keywords if kw in text)

    def _rerank_by_age_group(
        self,
        documents: list[str],
        metadatas: list[dict[str, Any]],
        age_group: str | None,
    ) -> list[str]:
        """
        Order documents by age-group match alone, stable within equal scores.

        A metadata heuristic, not a model — retained for direct use and tests.
        The live path calls `_ranked_indices`, which applies this only as a
        tie-breaker behind the cross-encoder.
        """
        if not age_group or not self._AGE_KEYWORDS.get(age_group.lower()):
            return documents

        order = sorted(
            range(len(documents)),
            key=lambda i: (
                -self._age_score(metadatas[i] if i < len(metadatas) else {}, age_group),
                i,
            ),
        )
        return [documents[i] for i in order]


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
