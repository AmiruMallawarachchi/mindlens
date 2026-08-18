"""
Session Memory Save
===================
Persists the current turn to MongoDB after all agents have run.
No LLM calls. Background utility agent.

Also does the actual extraction behind the Memory page's promise that
mentioning a person or a hard topic makes it show up there. Before this,
`user_memory` was fully readable and editable but nothing ever wrote to it
automatically — the "What's been hard" / "What's helped" categories could
only be filled by an admin-only endpoint, and a new person could only enter
memory through the onboarding wizard, never from an ordinary conversation.

Deliberately heuristic, not an LLM call: this is a *write* path whose output
gets replayed into every future prompt via memory_recall.py's "You've
mentioned {name} before" — a bad write here doesn't cost one turn, it
persists. Free-form model output is exactly the wrong shape for something
that gets stored and re-read; a small fixed vocabulary for topics/coping and
a narrow, tightly-bounded regex for names bounds what can ever be written,
the same way PersonalityAgent's keyword lists bound its own score updates.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from app.agents.base_agent import AgentContext, AgentOutput, BaseAgent

# A small set of relationship words a person is plausibly introduced with.
# Kept narrow on purpose — this is the only thing standing between "my
# roommate Alex" and treating any capitalised word as a person.
_RELATIONS = (
    "mom|mother|dad|father|sister|brother|best friend|friend|partner|"
    "boyfriend|girlfriend|husband|wife|colleague|coworker|boss|teacher|"
    "roommate|therapist|cousin|aunt|uncle|grandmother|grandfather|"
    "grandma|grandpa|son|daughter|manager|supervisor"
)
# "my sister Amaya" / "My best friend, Alex" — "my"/the relation word are
# matched case-insensitively (scoped inline flag, Python 3.11+) since "My"
# is routinely capitalized at the start of a sentence; the name itself stays
# case-sensitive, since a leading capital is the actual signal it's a name.
# A name may be two capitalised tokens: "Dr Perera", "Mary Jane".
# Capturing only the first meant "my supervisor Dr Perera" was stored as
# the person "Dr" -- so every later mention of Perera recalled nothing,
# and the Memory page listed a title as a person.
_NAME = r"[A-Z][a-zA-Z']{1,20}(?:\s+[A-Z][a-zA-Z']{1,20})?"

_RE_PERSON_FORWARD = re.compile(
    rf"\b(?i:my ({_RELATIONS}))\s*,?\s+({_NAME})\b"
)
# "Amaya, my sister" / "Alex my best friend"
_RE_PERSON_REVERSE = re.compile(
    rf"\b({_NAME}),?\s+(?i:my\s+({_RELATIONS}))\b"
)

# Canonical topic label -> the words that count as a mention of it. Narrow
# and closed on purpose (see module docstring) — this can only ever write
# one of these labels, never arbitrary text pulled from the message.
_TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "exams": ("exam", "exams", "viva", "finals", "midterm", "midterms"),
    "the dissertation": ("dissertation", "thesis"),
    "work": ("work", "job", "workplace", "my boss", "my manager"),
    "deadlines": ("deadline", "deadlines"),
    "a breakup": ("breakup", "broke up", "the breakup"),
    "an argument": ("argument", "fight with", "we fought"),
    "family": ("my family", "my parents"),
    "money": ("money", "finances", "financial", "rent", "bills"),
    "health": ("my health", "my diagnosis", "the hospital"),
    "sleep": ("insomnia", "can't sleep", "not sleeping"),
    "loneliness": ("lonely", "loneliness", "no one to talk to"),
    "grades": ("my grades", "my gpa", "failing"),
    "an interview": ("interview", "job interview"),
}

# Canonical coping label -> the words that name the strategy. Only recorded
# when a "helped" phrase (below) also appears in the same message.
_COPING_KEYWORDS: dict[str, tuple[str, ...]] = {
    "going for a walk": ("walk", "walking", "went for a walk"),
    "journaling": ("journaling", "journalling", "writing it down", "my journal"),
    "listening to music": ("music", "a playlist", "listening to songs"),
    "breathing exercises": ("breathing exercise", "deep breaths", "breathing exercises"),
    "meditation": ("meditation", "meditating"),
    "exercise": ("exercise", "the gym", "working out", "a run", "running"),
    "yoga": ("yoga",),
    "calling a friend": ("called a friend", "calling a friend", "talked to a friend"),
}
_HELPED_PHRASES = ("helped", "helps me", "helped me", "worked for me", "calmed me down")


def _normalize_name(name: str) -> str:
    """Title-case each word — so "AMAYA", "amaya" and "Amaya" collapse to
    the same `people` key instead of becoming three separate entries the
    Memory page's `$exists: False` guard can't tell apart.

    Per word, not per string: a single pass over the whole thing turned
    "Dr Perera" into "Dr perera"."""
    return " ".join(w[:1].upper() + w[1:].lower() for w in name.split())


def _extract_person(text_lower: str, text: str) -> tuple[str, str] | None:
    """Return (relation, name) for the first plausible new person mentioned,
    or None. Checked against `memory.people` by the caller before writing —
    this function only proposes, it never knows what's already on file."""
    match = _RE_PERSON_FORWARD.search(text)
    if match:
        return match.group(1).lower(), _normalize_name(match.group(2))
    match = _RE_PERSON_REVERSE.search(text)
    if match:
        return match.group(2).lower(), _normalize_name(match.group(1))
    return None


def _extract_topic(text_lower: str, distress_level: float, is_negative: bool) -> str | None:
    """A topic only counts as 'hard' alongside a genuinely negative turn —
    otherwise "exams" mentioned in passing ("exams are done, I'm relieved")
    would get flagged as a hard topic from the keyword alone."""
    if distress_level < 0.5 and not is_negative:
        return None
    for label, keywords in _TOPIC_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return label
    return None


def _extract_coping(text_lower: str) -> str | None:
    if not any(phrase in text_lower for phrase in _HELPED_PHRASES):
        return None
    for label, keywords in _COPING_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return label
    return None


class SessionMemorySave(BaseAgent):
    """
    Saves the completed turn to the sessions collection in MongoDB.
    Updates the user_memory document with longitudinal data.
    """

    def __init__(self) -> None:
        super().__init__(
            name="session_memory_save",
            description="Persist session turn to MongoDB",
            llm_tier="none",
            max_tokens=0,
            always_runs=False,
        )

    async def run(self, ctx: AgentContext) -> AgentOutput:
        """
        Return save metadata, including any memory extracted from this turn.
        The actual DB writes happen in the session router after this output
        (chat.py: _save_turn, _save_extracted_memory).
        """
        extracted: dict[str, str] = {}

        # "Nothing" turns off recall in memory_recall.py; it turns off this
        # extraction too — a user who asked MindLens not to draw on memory
        # shouldn't have new memory quietly accumulating in the background.
        if ctx.eos.memory_depth != "nothing":
            text = ctx.user_text
            text_lower = text.lower()

            # Person extraction runs on the RAW message, not the anonymized
            # one. anonymize() replaces titled/capitalised names ("Dr
            # Perera") with "[NAME]" before ctx.user_text is built -- correct
            # for anything that reaches Groq or leaves this process, but it
            # meant this regex could never see a real name to store. This
            # never leaves the server: it only ever becomes a key in this
            # user's own people graph.
            raw = ctx.raw_user_text
            person = _extract_person(raw.lower(), raw)
            if person:
                extracted["person_relation"] = person[0]
                extracted["person_name"] = person[1]

            is_negative = ctx.eos.valence == "negative"
            topic = _extract_topic(text_lower, ctx.eos.distress_level, is_negative)
            if topic:
                extracted["trigger_topic"] = topic

            coping = _extract_coping(text_lower)
            if coping:
                extracted["effective_coping"] = coping

        return AgentOutput(
            agent_name=self.name,
            text="",  # No user-facing text
            metadata={
                "llm_tier": "none",
                "action": "save_turn",
                "session_id": ctx.eos.session_id,
                "surface_emotion": ctx.eos.surface_emotion,
                "distress_level": ctx.eos.distress_level,
                "modality": ctx.eos.modality.value,
                "timestamp": datetime.now(UTC).isoformat(),
                "extracted": extracted,
            },
        )
