"""Metadata-only Langfuse tracing for hosted graph runs."""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class _TraceContext:
    def __init__(self, state: dict[str, Any]) -> None:
        self.state = state
        self.observation = None
        self._client = None

    def __enter__(self):
        if not settings.langfuse_enabled:
            return self
        try:
            from langfuse import Langfuse, get_client

            Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_base_url,
            )
            self._client = get_client()
            self.observation = self._client.start_as_current_observation(
                name="mindlens.turn",
                as_type="span",
                metadata={"graph": "mindlens_v2", "environment": settings.app_env},
            )
            self.observation.__enter__()
        except Exception as exc:
            logger.debug("Langfuse unavailable: %s", exc)
            self.observation = None
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.observation is not None:
            try:
                self.observation.update(
                    metadata={
                        "node_count": len(self.state.get("graph_nodes", [])),
                        "nodes": self.state.get("graph_nodes", []),
                        "route": self.state.get("route", ""),
                        "crisis": bool(self.state.get("crisis_flag")),
                        "degraded": self.state.get("degraded", []),
                        "rag_status": self.state.get("telemetry", {}).get("rag", {}).get("status"),
                        "llm_calls": self.state.get("llm_calls", []),
                    }
                )
                self.observation.__exit__(exc_type, exc, tb)
                if self._client:
                    self._client.flush()
            except Exception as trace_exc:
                logger.debug("Langfuse flush failed: %s", trace_exc)
        return False


def trace_graph(state: dict[str, Any]):
    """Return a trace context that never receives raw user content."""
    return _TraceContext(state)
