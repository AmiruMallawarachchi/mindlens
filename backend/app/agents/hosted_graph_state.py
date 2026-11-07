"""Shared graph state and normalization helpers."""

import json
import re
from typing import Any, TypedDict

from app.core.anonymizer import anonymize
from app.core.emotional_os import EmotionalOperatingState, Modality
from app.core.memory_recall import recall_for_turn


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


# gpt-oss answers `distress_level` as a word — "high", "moderate", "low" —
# more often than as a number, however the prompt is phrased. float("high")
# raises, the old except returned the 0.0 default, and every downstream
# consumer silently read "no distress": the review branch never fired, DBT was
# unreachable, mood_logs stayed flat, and the Progress page computed
# (1 - 0.0) * 10 = 10.0/10 for someone who had not slept in three days.
# This map is the fix at the model boundary, where drift has to be expected.
_WORD_SCALE: dict[str, float] = {
    "none": 0.0,
    "no": 0.0,
    "minimal": 0.05,
    "negligible": 0.05,
    "very low": 0.1,
    "slight": 0.25,
    "low": 0.2,
    "mild": 0.3,
    "some": 0.4,
    "moderate": 0.5,
    "moderately": 0.5,
    "medium": 0.5,
    "mid": 0.5,
    "elevated": 0.6,
    "notable": 0.65,
    "marked": 0.75,
    "high": 0.8,
    "intense": 0.85,
    "very high": 0.9,
    "severe": 0.9,
    "extreme": 0.95,
    "critical": 0.95,
    "overwhelming": 0.95,
}


def _number(value: Any, default: float = 0.0) -> float:
    """Coerce a hosted model's idea of a 0-1 magnitude into a float.

    Accepts numbers, numeric strings, percentages, fractions and the word
    scale above. Anything genuinely unparseable keeps the caller's default —
    but a word is not unparseable, and treating it as such was the bug.
    """
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return max(0.0, min(1.0, float(value)))
    if isinstance(value, str):
        text = value.strip().lower().replace("_", " ").replace("-", " ")
        if not text:
            return default
        percent = re.fullmatch(r"(\d{1,3})\s*%", text)
        if percent:
            return max(0.0, min(1.0, int(percent.group(1)) / 100))
        fraction = re.fullmatch(r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)", text)
        if fraction:
            numerator, denominator = float(fraction.group(1)), float(fraction.group(2))
            if denominator:
                return max(0.0, min(1.0, numerator / denominator))
        try:
            return max(0.0, min(1.0, float(text)))
        except ValueError:
            pass
        # Multi-word answers ("moderately high", "mild to moderate") take the
        # strongest word they contain: over-reading distress costs a safety
        # review, under-reading costs the thing being measured. Whole words
        # only, so "no" inside "know" never scores anything.
        hits = [
            score
            for phrase, score in _WORD_SCALE.items()
            if re.search(rf"\b{re.escape(phrase)}\b", text)
        ]
        if hits:
            return max(hits)
    return default


_TRUTHY_WORDS = frozenset(
    {"true", "yes", "y", "1", "high", "present", "flagged", "severe", "extreme", "critical", "acute", "imminent"}
)
_FALSY_WORDS = frozenset({"false", "no", "n", "0", "none", "low", "absent"})


def _flag(value: Any, default: bool = False) -> bool:
    """Coerce a hosted model's idea of a boolean.

    bool("false") is True, so the previous direct cast would have turned a
    model saying "crisis_risk": "false" into a crisis escalation.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in _TRUTHY_WORDS:
            return True
        if text in _FALSY_WORDS:
            return False
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value > 0
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
        crisis_escalating=_flag(assessment.get("crisis_risk")),
        session_turn_count=len(state.get("session_history", [])),
        valence=str(assessment.get("valence") or "neutral"),
        distortion_label=assessment.get("distortion_label"),
        distortion_score=_number(assessment.get("distortion_score"), 0.0),
    ).model_dump(mode="json")


def _recall_context(state: HostedGraphState) -> tuple[list[str], dict[str, Any]]:
    """Memory signals and typed preferences relevant to this turn.

    Signals return nothing when memory is empty, nothing on file matches, or
    the user chose memory_depth="nothing" — see core/memory_recall.py.
    Preferences are settings the user typed (tone, personality, custom
    instructions), so recall keeps them even under "nothing" and they are
    returned separately for the specialist prompt.
    """
    eos = state.get("eos", {})
    recall = recall_for_turn(
        state.get("memory") or {},
        user_text=anonymize(state["user_text"]),
        surface_emotion=str(eos.get("surface_emotion") or "neutral"),
        core_emotion=eos.get("core_emotion"),
    )
    preferences = {
        "preferred_modality": recall.preferred_modality,
        "tone_preference": recall.tone_preference,
        "personality": recall.personality,
        "custom_instructions": recall.custom_instructions,
    }
    return recall.memory_recalled, {key: value for key, value in preferences.items() if value}


def _specialist_context(state: HostedGraphState) -> dict[str, Any]:
    """The JSON the specialist sees: this turn, recent history, recalled
    context, curated notes, the assessment, and typed preferences."""
    eos = state.get("eos", {})
    return {
        "message": anonymize(state["user_text"]),
        "history": [anonymize(str(t.get("text", ""))) for t in state.get("session_history", [])[-6:]],
        "memory_signals": state.get("memory_recalled", []),
        "therapy_notes": state.get("rag_chunks", [])[:5],
        "assessment": state.get("assessment", {}),
        "preferences": {
            key: eos.get(key)
            for key in ("preferred_modality", "tone_preference", "personality", "custom_instructions")
            if eos.get(key)
        },
    }


