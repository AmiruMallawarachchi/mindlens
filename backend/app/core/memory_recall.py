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
    # Settings > General. Both shape how the reply is written, so they ride
    # along with the rest of the per-turn personalisation rather than being
    # fetched separately by the agent.
    personality: str | None = None
    custom_instructions: str | None = None
    # Onboarding step 3 (morning/evening/whenever) — CheckInScheduler reads
    # this off the EOS to decide *when* a check-in lands, not just *whether*
    # distress warrants one.
    checkin_preferred_time: str | None = None
    # Standing social disposition (0.0 introvert … 1.0 extrovert), inferred by
    # PersonalityAgent across sessions. RoutineAgent reads it off the EOS to
    # decide whether to suggest solo or social activities. None means nothing
    # has been inferred yet, which is different from a genuine 0.5.
    introvert_score: float | None = None
    # Your Mindlens > Memory depth (design.md §4.2). Carried through onto the
    # EOS so SessionMemorySave can also honour "nothing" — not just recall.
    memory_depth: str = "everything"


def _coerce_score(value: Any) -> float | None:
    """Read a stored 0..1 score, ignoring anything malformed.

    Returns None rather than a default when absent or out of range, so a
    never-inferred profile stays distinguishable from a genuine 0.5.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    score = float(value)
    return score if 0.0 <= score <= 1.0 else None


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
    personality = preferences.get("personality") or None
    custom_instructions = preferences.get("custom_instructions") or None
    # Your Mindlens studio's Memory depth control (design.md §4.2): "Nothing"
    # means the user asked MindLens not to draw on anything from before —
    # honour that before computing any recall at all, not just at display time.
    memory_depth = preferences.get("memory_depth") or "everything"
    checkin_preferred_time = preferences.get("checkin_preferred_time") or None
    introvert_score = _coerce_score(preferences.get("introvert_score"))
    if memory_depth == "nothing":
        # "Nothing" turns off *recall of past conversations*. It deliberately
        # does not disable personality, tone or custom instructions: those are
        # settings the user typed on purpose, not things MindLens remembered
        # about them, and silently ignoring them would be the wrong reading of
        # the control.
        #
        # introvert_score is on the other side of that line and is therefore
        # withheld here: nobody typed it, MindLens inferred it from things the
        # user said in past sessions. Applying it under "nothing" would be
        # drawing on remembered material while telling the user we aren't.
        return MemoryRecall(
            preferred_modality=preferred_modality,
            tone_preference=tone_preference,
            personality=personality,
            custom_instructions=custom_instructions,
            checkin_preferred_time=checkin_preferred_time,
            memory_depth=memory_depth,
        )

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
            # personality and custom_instructions are settings the user typed
            # on purpose, not things MindLens remembered about them — the
            # same reasoning that keeps them under "nothing" above. This
            # branch omitted them, so choosing the *middle* depth silently
            # discarded instructions that the strictest depth honoured.
            personality=personality,
            custom_instructions=custom_instructions,
            checkin_preferred_time=checkin_preferred_time,
            introvert_score=introvert_score,
            memory_depth=memory_depth,
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
        personality=personality,
        custom_instructions=custom_instructions,
        checkin_preferred_time=checkin_preferred_time,
        introvert_score=introvert_score,
        memory_depth=memory_depth,
    )
