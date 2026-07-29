"""Lazy, observable Hugging Face model registry."""

from __future__ import annotations

import asyncio
import datetime
from collections.abc import Callable
from typing import Any, cast

import torch
from transformers import Pipeline, pipeline

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

_DEVICE = 0 if torch.cuda.is_available() else -1
_TORCH_DTYPE = torch.float16 if torch.cuda.is_available() else torch.float32


class ModelManager:
    """Process-wide model registry with lazy loading and health metadata."""

    _instance: ModelManager | None = None
    _lock = asyncio.Lock()

    def __new__(cls) -> ModelManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            object.__setattr__(cls._instance, "_pipelines", {})
            object.__setattr__(cls._instance, "_health", {})
        return cls._instance

    def _record_error(self, name: str, exc: Exception, **extra: Any) -> dict[str, Any]:
        """
        Merge an error into `name`'s health entry, incrementing a running
        `error_count` rather than overwriting it. SYSTEM.md §13.4's admin
        Model Health Drawer requires "Error count" alongside status and
        latency; before this, each failure replaced the previous health
        entry outright, so only the most recent error was ever visible —
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
        **kwargs: Any,
    ) -> Pipeline:
        pipelines: dict[str, Pipeline] = object.__getattribute__(self, "_pipelines")
        if name in pipelines:
            return pipelines[name]

        health: dict[str, dict[str, Any]] = object.__getattribute__(self, "_health")
        health[name] = {
            "status": "loading",
            "model_id": model_id,
            "error_count": health.get(name, {}).get("error_count", 0),
        }
        logger.info("Loading model '%s' from %s", name, model_id)
        try:
            loaded = pipeline(
                task,
                model=model_id,
                tokenizer=model_id,
                device=_DEVICE,
                torch_dtype=_TORCH_DTYPE,
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

    async def _predict(
        self, name: str, accessor: Callable[[], Pipeline], text: str
    ) -> Any:
        started = asyncio.get_running_loop().time()
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(lambda: accessor()(text)),
                timeout=settings.model_inference_timeout_seconds,
            )
        except Exception as exc:
            self._record_error(name, exc)
            raise

        health: dict[str, dict[str, Any]] = object.__getattribute__(self, "_health")
        health[name] = {
            **health.get(name, {}),
            "status": "ready",
            "error": None,
            "last_inference_ms": round(
                (asyncio.get_running_loop().time() - started) * 1000, 2
            ),
        }
        return result

    async def predict_emotion(self, text: str) -> list[dict[str, Any]]:
        return cast(list[dict[str, Any]], await self._predict("emotion", self.emotion, text))

    async def predict_crisis(self, text: str) -> list[dict[str, Any]]:
        return cast(list[dict[str, Any]], await self._predict("crisis", self.crisis, text))

    async def predict_mental_health(self, text: str) -> list[dict[str, Any]]:
        return cast(
            list[dict[str, Any]],
            await self._predict("mental_health", self.mental_health, text),
        )

    async def predict_distortion(self, text: str) -> list[dict[str, Any]]:
        return cast(
            list[dict[str, Any]],
            await self._predict("distortion", self.distortion, text),
        )

    async def predict_all(self, text: str) -> dict[str, list[dict[str, Any]]]:
        """Run the three per-turn classifiers with isolated failure handling."""
        results = await asyncio.gather(
            self.predict_emotion(text),
            self.predict_crisis(text),
            self.predict_mental_health(text),
            self.predict_distortion(text),
            return_exceptions=True,
        )
        names = ("emotion", "crisis", "mental_health", "distortion")
        output: dict[str, list[dict[str, Any]]] = {}
        for name, result in zip(names, results, strict=True):
            if isinstance(result, BaseException):
                logger.error("%s model failed: %s", name, type(result).__name__)
                output[name] = []
            else:
                output[name] = result
        return output

    async def warmup_all(self) -> dict[str, dict[str, Any]]:
        """Load all configured models before accepting traffic."""
        accessors = (
            self.emotion,
            self.crisis,
            self.mental_health,
            self.distortion,
            self.rag_reranker,
        )
        results = await asyncio.gather(
            *(asyncio.to_thread(accessor) for accessor in accessors),
            return_exceptions=True,
        )
        failures = [result for result in results if isinstance(result, BaseException)]
        if failures:
            raise RuntimeError(f"Failed to load {len(failures)} configured model(s)")
        return self.health_status()

    def health_status(self) -> dict[str, dict[str, Any]]:
        health: dict[str, dict[str, Any]] = object.__getattribute__(self, "_health")
        configured = {
            "emotion": settings.EMOTION_MODEL_ID,
            "crisis": settings.CRISIS_MODEL_ID,
            "mental_health": settings.MH_MODEL_ID,
            "distortion": settings.DISTORTION_MODEL_ID,
            "rag_reranker": settings.RAG_RERANKER_MODEL_ID,
        }
        return {
            name: {
                "error_count": 0,
                **health.get(name, {"status": "not_loaded", "model_id": model_id}),
            }
            for name, model_id in configured.items()
        }


model_manager = ModelManager()
