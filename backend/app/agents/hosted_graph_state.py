"""Shared graph state and normalization helpers."""

import json
from typing import Any, TypedDict

from app.core.emotional_os import EmotionalOperatingState, Modality


class HostedGraphState(TypedDict, total=False):
    user_text: str
    user_name: str
    session_history: list[dict[str, Any]]
    memory: dict[str, Any] | None
    user_id: str | None
    on_stage: Any
    safety: dict[str, Any]
    crisis_flag: bool
    assessment: dict[str, Any]
    eos: dict[str, Any]
    route: str
    rag_chunks: list[str]
    response: str
    agent_outputs: list[dict[str, Any]]
    degraded: list[str]
    memory_recalled: list[str]
    telemetry: dict[str, Any]
    options: dict[str, Any] | None
    graph_nodes: list[str]
    review_required: bool
    llm_calls: list[dict[str, Any]]


def _clean_json(text: str) -> dict[str, Any]:
    """Parse a JSON object from a hosted model response."""
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("Groq returned no JSON object") from None
        value = json.loads(text[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("Groq returned a non-object JSON value")
    return value


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


async def _stage(state: HostedGraphState, name: str, detail: str) -> None:
    callback = state.get("on_stage")
    if callback:
        await callback(name, detail)


def _base_eos(state: HostedGraphState, assessment: dict[str, Any]) -> dict[str, Any]:
    emotion = str(assessment.get("surface_emotion") or "neutral")
    core = str(assessment.get("core_emotion") or emotion)
    distress = _number(assessment.get("distress_level"), 0.0)
    modality_name = str(assessment.get("modality") or ("DBT" if distress >= 0.7 else "CBT"))
    try:
        modality = Modality(modality_name)
    except ValueError:
        modality = Modality.CBT
    return EmotionalOperatingState(
        surface_emotion=emotion,
        surface_confidence=_number(assessment.get("surface_confidence"), 0.0),
        core_emotion=core,
        suppressed_emotion=assessment.get("suppressed_emotion"),
        distress_level=distress,
        emotional_stability=1.0 - distress,
        mental_fatigue=_number(assessment.get("mental_fatigue"), 0.3),
        modality=modality,
        crisis_escalating=bool(assessment.get("crisis_risk")),
        session_turn_count=len(state.get("session_history", [])),
        valence=str(assessment.get("valence") or "neutral"),
        distortion_label=assessment.get("distortion_label"),
        distortion_score=_number(assessment.get("distortion_score"), 0.0),
    ).model_dump(mode="json")


