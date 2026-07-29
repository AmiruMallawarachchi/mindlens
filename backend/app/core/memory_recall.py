"""
Memory recall — SYSTEM.md §13.3 requires the thinking panel to show
"Memory recalled". Nothing populated it: `user_memory` documents existed and
were fully readable/editable (app/routers/memory.py), but no turn ever read
one back in. `EmotionalOperatingState.people_graph` was likewise a real field
that nothing ever filled, so journaling_agent's people-graph personalisation
(SYSTEM.md §5.10, question 3) was dead code.

This module is pure and DB-free by design: it takes an already-fetched
`user_memory` document (or None) plus this turn's text and EOS reading, and
returns what should be merged into the EOS and what — if anything — is
genuinely relevant enough to surface as "recalled" this turn. A user with
memory on file but nothing relevant to *this* message gets an empty list,
not a fabricated one; that's a feature, not a gap — the panel says only what
actually applied.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.emotional_os import PeopleGraph

# Emotions worth surfacing a past coping strategy for. Deliberately narrow —
# offering "this helped before" on a calm turn reads as a non sequitur.
_DISTRESS_EMOTIONS = {"fear", "sadness", "anger", "nervousness", "grief", "annoyance", "disgust"}


@dataclass
class MemoryRecall:
    """What a turn's memory lookup produced."""

    people_graph: list[PeopleGraph] = field(default_factory=list)
    memory_recalled: list[str] = field(default_factory=list)
    preferred_modality: str | None = None
    tone_preference: str | None = None


def _people_from_doc(memory: dict[str, Any]) -> list[PeopleGraph]:
    """`user_memory.people` is {name: {role, context, sentiment}} — the shape
    onboarding.py's `_build_people_graph` writes. Reshape into the
    `PeopleGraph` list the EOS field expects."""
    raw_people = memory.get("people")
    if not isinstance(raw_people, dict):
        return []

    graph: list[PeopleGraph] = []
    for name, info in raw_people.items():
        if not name or not isinstance(info, dict):
            continue
        graph.append(
            PeopleGraph(
                name=name,
                relationship=info.get("role") or "someone close to you",
                context=info.get("context") or None,
            )
        )
    return graph


def recall_for_turn(
    memory: dict[str, Any] | None,
    *,
    user_text: str,
    surface_emotion: str,
    core_emotion: str | None,
) -> MemoryRecall:
    """
    Build this turn's memory context. `user_text` should be the anonymised
    turn text — anonymisation strips PII patterns (emails, phone numbers,
    addresses) but leaves ordinary words and names intact, which is what the
    keyword checks below need.
    """
    if not memory:
        return MemoryRecall()

    preferences = memory.get("preferences") or {}
    preferred_modality = preferences.get("preferred_modality") or None
    tone_preference = preferences.get("tone_preference") or None
    # Your Mindlens studio's Memory depth control (design.md §4.2): "Nothing"
    # means the user asked MindLens not to draw on anything from before —
    # honour that before computing any recall at all, not just at display time.
    memory_depth = preferences.get("memory_depth") or "everything"
    if memory_depth == "nothing":
        return MemoryRecall(preferred_modality=preferred_modality, tone_preference=tone_preference)

    people_graph = _people_from_doc(memory)
    lowered = user_text.lower()
    recalled: list[str] = []

    for person in people_graph:
        if person.name.lower() in lowered:
            recalled.append(f"You've mentioned {person.name} before — {person.relationship}.")

    # "Key details" surfaces people but not the deeper emotional-pattern
    # continuity below — a lighter middle ground between everything and
    # nothing.
    if memory_depth == "key_details":
        return MemoryRecall(
            people_graph=people_graph,
            memory_recalled=recalled,
            preferred_modality=preferred_modality,
            tone_preference=tone_preference,
        )

    patterns = memory.get("emotional_patterns") or {}

    for topic in patterns.get("trigger_topics") or []:
        if isinstance(topic, str) and topic and topic.lower() in lowered:
            recalled.append(f"{topic.capitalize()} has come up as a hard topic before.")

    common_emotion = patterns.get("most_common_emotion")
    if common_emotion and common_emotion in {surface_emotion, core_emotion}:
        recalled.append(f"{str(common_emotion).capitalize()} has been a common thread for you.")

    coping = patterns.get("effective_coping") or []
    if coping and (surface_emotion in _DISTRESS_EMOTIONS or core_emotion in _DISTRESS_EMOTIONS):
        recalled.append(f"{str(coping[0]).capitalize()} has helped before.")

    return MemoryRecall(
        people_graph=people_graph,
        memory_recalled=recalled,
        preferred_modality=preferred_modality,
        tone_preference=tone_preference,
    )
