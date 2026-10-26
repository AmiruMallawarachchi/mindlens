"""Memory recall and application of saved preferences to the EOS."""

from __future__ import annotations

from typing import Any

from app.core.emotional_os import EmotionalOperatingState, Modality
from app.core.memory_recall import recall_for_turn


def recall_and_apply_memory(
    memory: dict[str, Any] | None,
    *,
    user_text: str,
    eos: EmotionalOperatingState,
    crisis_flag: bool,
):
    recall = recall_for_turn(
        memory,
        user_text=user_text,
        surface_emotion=eos.surface_emotion,
        core_emotion=eos.core_emotion,
    )
    if not crisis_flag:
        eos.people_graph = recall.people_graph
        # Style preferences only apply outside a crisis — a crisis reply
        # comes from vetted templates and must not be restyled by anything
        # the user typed into settings.
        eos.personality = recall.personality
        eos.custom_instructions = recall.custom_instructions
        eos.checkin_preferred_time = recall.checkin_preferred_time
        # Settings > General > Tone (Gentle/Balanced/Direct). Read by
        # empathy_agent's tone_instruction branch — without this
        # assignment the setting saved and round-tripped correctly but
        # never reached the EOS, so it changed nothing about the reply.
        if recall.tone_preference:
            eos.tone_preference = recall.tone_preference  # type: ignore[assignment]
        # Settings > Memory depth. Read by SessionMemorySave to also gate
        # its own extraction, not just recall — see MemoryRecall.memory_depth.
        if recall.memory_depth in {"everything", "key_details", "nothing"}:
            eos.memory_depth = recall.memory_depth  # type: ignore[assignment]
        # The standing social profile RoutineAgent branches on. Without
        # this the EOS is rebuilt at its 0.5 default every turn, so
        # RoutineAgent's <0.4 / >0.7 branches could never fire and
        # PersonalityAgent scored every update from a blank slate.
        # Non-crisis only, for the same reason as the style preferences.
        if recall.introvert_score is not None:
            eos.introvert_score = recall.introvert_score
        # A stated modality preference wins over the distress-based
        # default, but never over the high-distress DBT escalation —
        # a standing preference shouldn't block the safer choice.
        if recall.preferred_modality and eos.distress_level <= 0.7:
            try:
                eos.modality = Modality(recall.preferred_modality)
            except ValueError:
                pass
    return recall
