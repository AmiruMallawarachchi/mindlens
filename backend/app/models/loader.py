"""Lazy, observable Hugging Face model registry."""

from __future__ import annotations

import asyncio
import datetime
import gc
import os
from collections.abc import Callable
from typing import Any, cast

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

PipelineLike = Callable[[str], Any]


class OnnxTextClassificationPipeline:
    """Small ONNX Runtime text-classification wrapper for Render Free."""

    def __init__(
        self,
        model_dir: str,
        *,
        top_k: int | None,
        max_length: int = 512,
    ) -> None:
        import numpy as np
        import onnxruntime as ort
        from transformers import AutoConfig, AutoTokenizer

        self._np = np
        self._session = ort.InferenceSession(
            os.path.join(model_dir, "model.onnx"),
            providers=["CPUExecutionProvider"],
        )
        self._tokenizer = AutoTokenizer.from_pretrained(
            model_dir,
            local_files_only=True,
        )  # nosec B615
        self._config = AutoConfig.from_pretrained(
            model_dir,
            local_files_only=True,
        )  # nosec B615
        self._top_k = top_k
        self._max_length = max_length

    def __call__(self, text: str) -> list[dict[str, Any]]:
        encoded = self._tokenizer(
            text,
            return_tensors="np",
            truncation=True,
            max_length=self._max_length,
        )
        inputs = {
            item.name: encoded[item.name]
            for item in self._session.get_inputs()
            if item.name in encoded
        }
        logits = self._session.run(None, inputs)[0][0]
        scores = self._softmax(logits)
        id2label = getattr(self._config, "id2label", {}) or {}
        ranked = sorted(
            enumerate(scores.tolist()),
            key=lambda item: item[1],
            reverse=True,
        )
        if self._top_k is not None:
            ranked = ranked[: self._top_k]
        return [
            {"label": str(id2label.get(idx, f"LABEL_{idx}")), "score": float(score)}
            for idx, score in ranked
        ]

    def _softmax(self, logits: Any) -> Any:
        shifted = logits - self._np.max(logits)
        exp = self._np.exp(shifted)
        return exp / self._np.sum(exp)


class ModelManager:
    """Process-wide model registry with lazy loading and health metadata."""

    _instance: ModelManager | None = None
    _lock = asyncio.Lock()

    def __new__(cls) -> ModelManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            object.__setattr__(cls._instance, "_pipelines", {})
            object.__setattr__(cls._instance, "_health", {})
            object.__setattr__(cls._instance, "_resident_model", None)
        return cls._instance

    def _load_pipeline(
        self,
        name: str,
        model_id: str,
        task: str,
        *,
        top_k: int | None = 1,
        **kwargs: Any,
    ) -> PipelineLike:
        pipelines: dict[str, PipelineLike] = object.__getattribute__(self, "_pipelines")
        if name in pipelines:
            return pipelines[name]

        if settings.is_render_free_demo:
            self._unload_all(except_name=name)

        health: dict[str, dict[str, Any]] = object.__getattribute__(self, "_health")
        backend = settings.model_backend
        health[name] = {"status": "loading", "model_id": model_id, "backend": backend}
        logger.info("Loading model '%s' from %s using %s", name, model_id, backend)
        try:
            if backend == "disabled":
                raise RuntimeError("Model backend disabled")
            if backend == "onnx":
                loaded = self._load_onnx_pipeline(name, model_id, task, top_k, **kwargs)
            else:
                loaded = self._load_pytorch_pipeline(model_id, task, top_k, **kwargs)
        except Exception as exc:
            health[name] = {
                "status": "error",
                "model_id": model_id,
                "backend": backend,
                "error": type(exc).__name__,
            }
            raise

        pipelines[name] = loaded
        object.__setattr__(self, "_resident_model", name)
        health[name] = {
            "status": "ready",
            "model_id": model_id,
            "backend": backend,
            "loaded_at": datetime.datetime.now(datetime.UTC).isoformat(),
        }
        logger.info("Model '%s' loaded successfully", name)
        return loaded

    def _load_pytorch_pipeline(
        self,
        model_id: str,
        task: str,
        top_k: int | None,
        **kwargs: Any,
    ) -> PipelineLike:
        import torch
        from transformers import pipeline

        device = 0 if torch.cuda.is_available() else -1
        torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        return cast(
            PipelineLike,
            pipeline(
                task,
                model=model_id,
                tokenizer=model_id,
                device=device,
                torch_dtype=torch_dtype,
                top_k=top_k,
                **kwargs,
            ),
        )

    def _load_onnx_pipeline(
        self,
        name: str,
        model_id: str,
        task: str,
        top_k: int | None,
        **kwargs: Any,
    ) -> PipelineLike:
        model_dir = os.path.join(settings.render_free_model_dir, name)
        onnx_file = os.path.join(model_dir, "model.onnx")
        if not os.path.exists(onnx_file):
            raise FileNotFoundError(
                f"ONNX artifact missing for {name}; expected {onnx_file}"
            )

        _ = (model_id, task)
        max_length = int(kwargs.get("max_length", 512))
        return OnnxTextClassificationPipeline(
            model_dir,
            top_k=top_k,
            max_length=max_length,
        )

    def _unload_all(self, *, except_name: str | None = None) -> None:
        pipelines: dict[str, PipelineLike] = object.__getattribute__(self, "_pipelines")
        health: dict[str, dict[str, Any]] = object.__getattribute__(self, "_health")
        for name in list(pipelines):
            if name == except_name:
                continue
            pipelines.pop(name, None)
            health[name] = {
                **health.get(name, {}),
                "status": "unloaded",
                "reason": "render_free_single_resident_model",
            }
        object.__setattr__(self, "_resident_model", next(iter(pipelines), None))
        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    def emotion(self) -> PipelineLike:
        return self._load_pipeline(
            "emotion",
            settings.EMOTION_MODEL_ID,
            "text-classification",
            top_k=None,
            truncation=True,
            max_length=512,
        )

    def crisis(self) -> PipelineLike:
        return self._load_pipeline(
            "crisis",
            settings.CRISIS_MODEL_ID,
            "text-classification",
            top_k=1,
            truncation=True,
            max_length=512,
        )

    def mental_health(self) -> PipelineLike:
        return self._load_pipeline(
            "mental_health",
            settings.MH_MODEL_ID,
            "text-classification",
            top_k=None,
            truncation=True,
            max_length=512,
        )

    def distortion(self) -> PipelineLike:
        return self._load_pipeline(
            "distortion",
            settings.DISTORTION_MODEL_ID,
            "text-classification",
            top_k=None,
            truncation=True,
            max_length=512,
        )

    def rag_reranker(self) -> PipelineLike:
        return self._load_pipeline(
            "rag_reranker",
            settings.RAG_RERANKER_MODEL_ID,
            "text-classification",
            top_k=1,
            truncation=True,
            max_length=512,
        )

    async def _predict(
        self, name: str, accessor: Callable[[], PipelineLike], text: str
    ) -> Any:
        started = asyncio.get_running_loop().time()
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(lambda: accessor()(text)),
                timeout=settings.model_inference_timeout_seconds,
            )
        except Exception as exc:
            health: dict[str, dict[str, Any]] = object.__getattribute__(self, "_health")
            health[name] = {
                **health.get(name, {}),
                "status": "error",
                "error": type(exc).__name__,
            }
            if settings.is_render_free_demo:
                logger.warning("%s model degraded in render_free_demo: %s", name, exc)
                return []
            raise
        health = object.__getattribute__(self, "_health")
        health[name] = {
            **health.get(name, {}),
            "status": "ready",
            "last_inference_ms": round(
                (asyncio.get_running_loop().time() - started) * 1000, 2
            ),
        }
        if settings.is_render_free_demo:
            self._unload_all()
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
        if settings.is_render_free_demo:
            results = []
            for predictor in (
                self.predict_emotion,
                self.predict_crisis,
                self.predict_mental_health,
                self.predict_distortion,
            ):
                results.append(await predictor(text))
        else:
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
            name: health.get(
                name,
                {
                    "status": "not_loaded",
                    "model_id": model_id,
                    "backend": settings.model_backend,
                },
            )
            for name, model_id in configured.items()
        }

    def resident_model_count(self) -> int:
        pipelines: dict[str, PipelineLike] = object.__getattribute__(self, "_pipelines")
        return len(pipelines)


model_manager = ModelManager()
