"""Lazy, observable Hugging Face model registry."""

from __future__ import annotations

import datetime
import threading
import time
from typing import Any

try:  # Legacy compatibility only. V2 never calls this registry.
    import torch
    from transformers import AutoTokenizer, Pipeline, pipeline
except ImportError:  # pragma: no cover - exercised only in hosted deployments
    torch = None  # type: ignore[assignment]
    AutoTokenizer = None  # type: ignore[assignment]
    Pipeline = Any  # type: ignore[misc,assignment]
    pipeline = None  # type: ignore[assignment]

from app.config import settings
from app.models.prediction_methods import ModelPredictionMethods
from app.utils.logger import get_logger

logger = get_logger(__name__)

_DEVICE = 0 if torch is not None and torch.cuda.is_available() else -1
_TORCH_DTYPE = (
    torch.float16 if torch is not None and torch.cuda.is_available() else None
)


def _score_of(item: Any) -> float:
    """Pull the scalar score out of one text-classification result.

    The pipeline wraps each result in a list when ``top_k`` is set and returns
    a bare dict when it isn't. Accept both rather than pinning the shape.
    """
    if isinstance(item, list):
        item = item[0]
    return float(item["score"])


class ModelManager(ModelPredictionMethods):
    """Process-wide model registry with lazy loading and health metadata."""

    _instance: ModelManager | None = None
    # A plain thread lock, not asyncio.Lock: `_load_pipeline` runs inside
    # `asyncio.to_thread` (see `_predict` and `warmup_all`), so callers for
    # different models are genuinely concurrent OS threads, not coroutines
    # on one event loop â€” an asyncio.Lock doesn't coordinate across threads.
    # Declared but never acquired anywhere before this: the first real turn
    # after startup fired 4 model loads across 4 threads simultaneously,
    # each independently building a multi-hundred-MB torch model under
    # shared memory pressure. Live-observed failure mode on this machine:
    # "Cannot copy out of meta tensor; no data!" â€” a load that lost the
    # race for memory partway through. Serializing the *loading* phase
    # (inference on already-loaded models stays fully concurrent) is what
    # this lock is for.
    _load_lock = threading.Lock()

    def __new__(cls) -> ModelManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            object.__setattr__(cls._instance, "_pipelines", {})
            object.__setattr__(cls._instance, "_health", {})
        return cls._instance

    def _record_error(self, name: str, exc: Exception, **extra: Any) -> dict[str, Any]:
        """
        Merge an error into `name`'s health entry, incrementing a running
        `error_count` rather than overwriting it. SYSTEM.md Â§13.4's admin
        Model Health Drawer requires "Error count" alongside status and
        latency; before this, each failure replaced the previous health
        entry outright, so only the most recent error was ever visible â€”
        a model that failed 50 times looked identical to one that failed
        once.
        """
        health: dict[str, dict[str, Any]] = object.__getattribute__(self, "_health")
        previous = health.get(name, {})
        entry = {
            **previous,
            "status": "error",
            "error": type(exc).__name__,
            "error_count": previous.get("error_count", 0) + 1,
            **extra,
        }
        health[name] = entry
        return entry

    def _load_pipeline(
        self,
        name: str,
        model_id: str,
        task: str,
        *,
        top_k: int | None = 1,
        tokenizer_model_input_names: list[str] | None = None,
        **kwargs: Any,
    ) -> Pipeline:
        if pipeline is None:
            raise RuntimeError("Local model inference was removed in MindLens V2; use hosted_graph")
        pipelines: dict[str, Pipeline] = object.__getattribute__(self, "_pipelines")
        if name in pipelines:
            return pipelines[name]

        health: dict[str, dict[str, Any]] = object.__getattribute__(self, "_health")

        # Serializes the *loading* phase only â€” see _load_lock's class-level
        # comment. Inference on already-loaded models never touches this
        # lock, so normal per-turn concurrency is unaffected; only the
        # narrow window of the first turn(s) after startup, where several
        # models are cold at once, is forced one-at-a-time.
        with self._load_lock:
            # Re-check: another thread may have finished loading this exact
            # model while this one was waiting for the lock.
            if name in pipelines:
                return pipelines[name]

            health[name] = {
                "status": "loading",
                "model_id": model_id,
                "error_count": health.get(name, {}).get("error_count", 0),
            }

            try:
                # `tokenizer_model_input_names` exists for the crisis model:
                # its HF repo pairs a BertTokenizerFast (which emits
                # token_type_ids by default) with a
                # DistilBertForSequenceClassification model (which has no
                # segment embeddings and rejects that kwarg outright) â€”
                # every real call raised, was swallowed by predict_all()'s
                # return_exceptions=True, and silently zeroed out the
                # classifier layer of crisis detection on every single turn.
                # Restricting the tokenizer's output keys at construction
                # time is the standard fix for this exact mismatch.
                #
                # `revision` pins which commit of the Hub repo is fetched.
                # Left implicit, from_pretrained takes whatever is at the
                # branch head *at download time*, so a compromised or simply
                # re-pushed repo silently changes the weights this app runs â€”
                # the supply-chain hole bandit's B615 flags. Per-model, so the
                # third-party emotion checkpoint can be pinned to an exact
                # commit while our own repos track a branch through retraining.
                revision = settings.model_revision_for(name)
                tokenizer = (
                    AutoTokenizer.from_pretrained(
                        model_id,
                        revision=revision,
                        model_input_names=tokenizer_model_input_names,
                    )
                    if tokenizer_model_input_names
                    else model_id
                )
                logger.info(
                    "Loading model '%s' from %s @ %s", name, model_id, revision
                )
                loaded = pipeline(
                    task,
                    model=model_id,
                    tokenizer=tokenizer,
                    revision=revision,
                    device=_DEVICE,
                    dtype=_TORCH_DTYPE,
                    top_k=top_k,
                    **kwargs,
                )
            except Exception as exc:
                self._record_error(name, exc, model_id=model_id)
                raise

            pipelines[name] = loaded

        health[name] = {
            "status": "ready",
            "model_id": model_id,
            "loaded_at": datetime.datetime.now(datetime.UTC).isoformat(),
            "error_count": health.get(name, {}).get("error_count", 0),
        }
        logger.info("Model '%s' loaded successfully", name)
        return loaded

    def emotion(self) -> Pipeline:
        return self._load_pipeline(
            "emotion",
            settings.EMOTION_MODEL_ID,
            "text-classification",
            top_k=None,
            truncation=True,
            max_length=512,
        )

    def crisis(self) -> Pipeline:
        return self._load_pipeline(
            "crisis",
            settings.CRISIS_MODEL_ID,
            "text-classification",
            top_k=1,
            truncation=True,
            max_length=512,
            # See _load_pipeline's comment â€” this model's tokenizer/
            # architecture pairing crashes on every call without it.
            tokenizer_model_input_names=["input_ids", "attention_mask"],
        )

    def mental_health(self) -> Pipeline:
        return self._load_pipeline(
            "mental_health",
            settings.MH_MODEL_ID,
            "text-classification",
            top_k=None,
            truncation=True,
            max_length=512,
        )

    def distortion(self) -> Pipeline:
        return self._load_pipeline(
            "distortion",
            settings.DISTORTION_MODEL_ID,
            "text-classification",
            top_k=None,
            truncation=True,
            max_length=512,
        )

    def rag_reranker(self) -> Pipeline:
        return self._load_pipeline(
            "rag_reranker",
            settings.RAG_RERANKER_MODEL_ID,
            "text-classification",
            top_k=1,
            truncation=True,
            max_length=512,
        )

    def rerank(self, query: str, documents: list[str]) -> list[float]:
        """Score each ``(query, document)`` pair with the cross-encoder.

        Synchronous on purpose: the only caller (``TherapyRetriever``) already
        runs inside a worker thread, and the whole candidate set goes through
        in a single batched call rather than one call per chunk.

        The head is ``num_labels=1``, so the pipeline emits one sigmoid score
        per pair and higher means more relevant.

        Raises on failure â€” the retriever decides whether to fall back, since
        it is the one that knows an empty ranking is survivable.
        """
        if not documents:
            return []

        started = time.perf_counter()
        try:
            pipe = self.rag_reranker()
            raw = pipe([{"text": query, "text_pair": doc} for doc in documents])
            scores = [_score_of(item) for item in raw]
        except Exception as exc:
            self._record_error("rag_reranker", exc)
            raise

        if len(scores) != len(documents):
            exc = ValueError(
                f"reranker returned {len(scores)} scores for {len(documents)} documents"
            )
            self._record_error("rag_reranker", exc)
            raise exc

        health: dict[str, dict[str, Any]] = object.__getattribute__(self, "_health")
        health["rag_reranker"] = {
            **health.get("rag_reranker", {}),
            "status": "ready",
            "error": None,
            "last_inference_ms": round((time.perf_counter() - started) * 1000, 2),
        }
        return scores

model_manager = ModelManager()
