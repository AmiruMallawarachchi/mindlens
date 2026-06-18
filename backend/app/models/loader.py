# backend/app/models/loader.py
"""
MindLens Model Loader
======================
Handles lazy loading, caching, and inference of all HuggingFace pipelines.
Ensures models are loaded once and reused across the application lifespan.
"""

from __future__ import annotations

import asyncio
from typing import Any, cast

import torch
from transformers import Pipeline, pipeline

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Hardware detection
# ---------------------------------------------------------------------------
_DEVICE = 0 if torch.cuda.is_available() else -1
_TORCH_DTYPE = torch.float16 if torch.cuda.is_available() else torch.float32


class ModelManager:
    """
    Singleton-style manager for all HF pipelines.
    Loads on first use; persists for the application lifetime.
    """

    _instance: ModelManager | None = None
    _lock = asyncio.Lock()

    def __new__(cls) -> ModelManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # Initialize storage dict inside __new__ to avoid Pylance
            # complaining about attribute access before __init__
            object.__setattr__(cls._instance, "_pipelines", {})
        return cls._instance

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _load_pipeline(
        self,
        name: str,
        model_id: str,
        task: str,
        *,
        top_k: int | None = 1,
        **kwargs: Any,
    ) -> Pipeline:
        """
        Load a transformers pipeline with consistent device/dtype settings.
        `top_k=None` is REQUIRED for multi-label classifiers (go-emotions)
        so that raw logits for all classes are returned.
        """
        # Use object.__getattribute__ to satisfy Pylance on the singleton
        pipelines: dict[str, Pipeline] = object.__getattribute__(self, "_pipelines")
        if name in pipelines:
            return pipelines[name]

        logger.info("Loading model '%s' from %s …", name, model_id)
        pipe = pipeline(
            task,
            model=model_id,
            tokenizer=model_id,
            device=_DEVICE,
            torch_dtype=_TORCH_DTYPE,
            top_k=top_k,
            **kwargs,
        )
        pipelines[name] = pipe
        logger.info("Model '%s' loaded successfully.", name)
        return pipe

    # -----------------------------------------------------------------------
    # Public accessors
    # -----------------------------------------------------------------------

    def emotion(self) -> Pipeline:
        """
        28-class multi-label emotion classifier (go-emotions).
        top_k=None → returns scores for ALL 28 classes simultaneously.
        """
        return self._load_pipeline(
            name="emotion",
            model_id=settings.EMOTION_MODEL_ID,
            task="text-classification",
            top_k=None,
            truncation=True,
            max_length=512,
        )

    def crisis(self) -> Pipeline:
        """
        Binary crisis detector (DistilBERT fine-tuned).
        top_k=1 → single highest-probability label is sufficient.
        """
        return self._load_pipeline(
            name="crisis",
            model_id=settings.CRISIS_MODEL_ID,
            task="text-classification",
            top_k=1,
            truncation=True,
            max_length=512,
        )

    def mental_health(self) -> Pipeline:
        """
        Multi-label mental-health condition classifier (MentalBERT).
        top_k=None → returns scores for all condition classes.
        """
        return self._load_pipeline(
            name="mental_health",
            model_id=settings.MH_MODEL_ID,
            task="text-classification",
            top_k=None,
            truncation=True,
            max_length=512,
        )

    # -----------------------------------------------------------------------
    # Async wrappers (non-blocking for FastAPI)
    # -----------------------------------------------------------------------

    async def predict_emotion(self, text: str) -> list[dict[str, Any]]:
        """Async wrapper; runs in thread pool to avoid blocking the event loop."""
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self.emotion(), text)
        return cast(list[dict[str, Any]], result)

    async def predict_crisis(self, text: str) -> list[dict[str, Any]]:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self.crisis(), text)
        return cast(list[dict[str, Any]], result)

    async def predict_mental_health(self, text: str) -> list[dict[str, Any]]:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self.mental_health(), text)
        return cast(list[dict[str, Any]], result)

    # -----------------------------------------------------------------------
    # Batch prediction helpers (used by orchestrator for parallel gather)
    # -----------------------------------------------------------------------

    async def predict_all(self, text: str) -> dict[str, list[dict[str, Any]]]:
        """
        Fire all three models concurrently via asyncio.gather.
        Total latency = max(individual latency), NOT the sum.
        """
        emotion_task = self.predict_emotion(text)
        crisis_task = self.predict_crisis(text)
        mh_task = self.predict_mental_health(text)

        emotion_result, crisis_result, mh_result = await asyncio.gather(
            emotion_task, crisis_task, mh_task
        )

        return {
            "emotion": emotion_result,
            "crisis": crisis_result,
            "mental_health": mh_result,
        }


# Module-level instance
model_manager = ModelManager()
