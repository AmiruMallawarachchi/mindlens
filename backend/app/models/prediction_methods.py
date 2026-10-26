"""Asynchronous prediction, warmup, and model health behavior."""

from __future__ import annotations

import asyncio
from typing import Any, Callable, cast

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger("app.models.loader")


class ModelPredictionMethods:
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

    # Any short, harmless string. Only used to prove a loaded pipeline can
    # actually run â€” the prediction itself is discarded.
    _SMOKE_TEXT = "hello"

    async def warmup_all(self) -> dict[str, dict[str, Any]]:
        """Load all configured models AND prove each one can run inference.

        Constructing a pipeline is not evidence that it works. A
        transformers/tokenizers version mismatch loads all five models
        cleanly and then raises on every single `pipeline(text)` call
        (`_batch_encode_plus() got an unexpected keyword argument
        'dtype'`). Because `predict_all` gathers with
        `return_exceptions=True`, each of those failures was swallowed into
        an empty score dict: emotion, mental-health and distortion all
        returned nothing, distress computed to 0.0 on every turn, and the
        crisis classifier â€” layer 2 of a safety gate that is supposed to be
        two layers â€” contributed nothing while the app reported itself
        healthy and `/ready` returned 200.

        Running one throwaway prediction per model at startup converts that
        from a silent, weeks-long degradation into a boot failure.
        """
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

        smoke: list[tuple[str, Any]] = [
            ("emotion", self.predict_emotion(self._SMOKE_TEXT)),
            ("crisis", self.predict_crisis(self._SMOKE_TEXT)),
            ("mental_health", self.predict_mental_health(self._SMOKE_TEXT)),
            ("distortion", self.predict_distortion(self._SMOKE_TEXT)),
            (
                "rag_reranker",
                asyncio.to_thread(self.rerank, self._SMOKE_TEXT, [self._SMOKE_TEXT]),
            ),
        ]
        smoke_results = await asyncio.gather(
            *(coro for _, coro in smoke), return_exceptions=True
        )
        broken = [
            f"{name} ({type(result).__name__}: {result})"
            for (name, _), result in zip(smoke, smoke_results, strict=True)
            if isinstance(result, BaseException)
        ]
        if broken:
            raise RuntimeError(
                "Model(s) loaded but cannot run inference: "
                + "; ".join(broken)
                + ". This usually means the installed transformers/tokenizers "
                "versions do not match requirements.txt."
            )
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

