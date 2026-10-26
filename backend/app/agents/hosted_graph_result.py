"""Serialization helpers for the hosted graph's stable result contract."""

from typing import Any

from app.core.emotional_os import EmotionalOperatingState
from app.agents.hosted_graph_state import HostedGraphState


def result_contract(state: HostedGraphState) -> dict[str, Any]:
    crisis = bool(state.get("crisis_flag"))
    agents = ["crisis"] if crisis else [state.get("route", "empathy")]
    return {
        "eos": state.get("eos", EmotionalOperatingState().model_dump(mode="json")),
        "agents": agents,
        "crisis_flag": crisis,
        "assembled_text": state.get("response", ""),
        "agent_outputs": state.get("agent_outputs", []),
        "safety": state.get("safety", {"is_crisis": False}),
        "degraded": sorted(set(state.get("degraded", []))),
        "memory_recalled": state.get("memory_recalled", []),
        "options": None,
        "telemetry": {
            **state.get("telemetry", {}),
            "graph": {"nodes": state.get("graph_nodes", []), "route": state.get("route", "empathy")},
            "llm": {
                "calls": state.get("llm_calls", []),
                "count": len(state.get("llm_calls", [])),
            },
            "substantive": len(state.get("user_text", "").split()) >= 4,
        },
    }

def llm_call_metadata(stage: str, response: Any) -> dict[str, Any]:
    """Keep provider telemetry JSON-safe and free of prompts or outputs."""
    def safe_number(value: Any) -> int | None:
        return value if isinstance(value, int | float) else None

    return {
        "stage": stage,
        "model": str(getattr(response, "model_used", "unknown")),
        "tokens": safe_number(getattr(response, "tokens_used", None)),
        "latency_ms": safe_number(getattr(response, "latency_ms", None)),
    }


_hosted_orchestrator: HostedGraphOrchestrator | None = None

