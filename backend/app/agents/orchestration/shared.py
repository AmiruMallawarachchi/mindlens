"""Shared policy and callback types for the legacy orchestrator pipeline."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

DISTORTION_LABEL_MAP = {
    "LABEL_0": "catastrophizing",
    "LABEL_1": "mind_reading",
    "LABEL_2": "all_or_nothing",
    "LABEL_3": "personalization",
    "LABEL_4": "overgeneralization",
    "LABEL_5": "emotional_reasoning",
    "LABEL_6": "should_statements",
    "LABEL_7": "jumping_to_conclusions",
    "LABEL_8": "magnification",
    "LABEL_9": "mental_filter",
}

StageCallback = Callable[[str, str], Awaitable[None]]

# Bookkeeping agents are omitted from user-facing progress summaries.
_SILENT_AGENTS = frozenset({"personality", "checkin_scheduler", "session_memory_save"})
_SUBSTANTIVE_WORD_COUNT = 4
MODALITY_DRIVEN_AGENTS = frozenset({"distortion", "challenge", "reflection"})


def turn_is_substantive(user_text: str, distress_level: float) -> bool:
    """Whether a turn has enough content or distress for RAG and therapy agents."""
    if distress_level >= 0.5:
        return True
    return len(user_text.split()) >= _SUBSTANTIVE_WORD_COUNT
