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
# Longer forms first: the alternation is ordered, so "mother" must precede
# "mom" or "my mother Rehana" matches "mom" and leaves a stray "her".
# "mum"/"mummy" are here because this app's users are Sri Lankan, where the
# British spelling is the common one — listing only "mom" meant "my mum's
# name is Rehana" recorded nobody.
_RELATIONS = (
    "grandmother|grandfather|girlfriend|boyfriend|supervisor|colleague|"
    "therapist|roommate|coworker|daughter|partner|brother|husband|teacher|"
    "manager|grandma|grandpa|mother|sister|cousin|mummy|father|"
    "best friend|friend|uncle|aunt|boss|wife|son|mommy|daddy|papa|"
    "mom|mum|dad"
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

# The connector between the relation and the name. Only bare adjacency
# ("my sister Amaya"), an explicit naming verb ("my boyfriend called
# Hasanka"), or an explicit "name is" ("my mum's name is Rehana") count.
#
# A bare "is" is deliberately NOT accepted. "my mum is Rehana" would be a
# real hit, but "my mum is Sri Lankan" / "my dad is Buddhist" are the same
# shape, and a capitalised word after "is" is far more often a nationality,
# faith or adjective than a name — which would file one as a person and
# then replay it into every future prompt as "You've mentioned Sri Lankan
# before". Missing a name costs one un-saved fact the user can add in
# Memory; inventing one is a write that persists and quietly corrupts
# recall, so the asymmetry decides it.
_CONNECTOR = (
    r"\s*,?"  # "my sister Amaya" / "my best friend, Alex"
    r"|\s+(?:called|named)"  # "my boyfriend called Hasanka"
    r"|'?s?\s+name\s+is"  # "my mum's name is Rehana" / "my mums name is Rehana"
)

_RE_PERSON_FORWARD = re.compile(
    rf"\b(?i:my\s+({_RELATIONS})(?:{_CONNECTOR}))\s+({_NAME})\b"
)

# "I have a boyfriend called Hasanka" — the indefinite article is just as
# common as "my" when someone introduces a person for the first time, which
# is exactly the turn this needs to catch. Restricted to the explicit
# naming connectors: "a friend called Alex" is unambiguous, whereas bare
# adjacency after "a" ("a sister Amaya") is not idiomatic and would only
# widen the false-positive surface for no real gain.
_RE_PERSON_ARTICLE = re.compile(
    rf"\b(?i:an?\s+({_RELATIONS})(?:\s+(?:called|named)|'?s?\s+name\s+is))\s+({_NAME})\b"
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


# One turn introducing more than a handful of people is far more likely to
# be pasted text or an attempt to bulk-write the graph than a real
# introduction, so the write is bounded rather than unbounded.
_MAX_PEOPLE_PER_TURN = 3


def _extract_people(text: str) -> list[tuple[str, str]]:
    """Return every (relation, name) plausibly introduced in this message.

    Deliberately not just the first: "I have a boyfriend called Hasanka and
    my mum's name is Rehana" is one ordinary sentence introducing two
    people, and returning only one silently dropped the other — the user
    had said "remember those people" and half of them were never written.

    Order is preserved and names are de-duplicated case-insensitively, so a
    message that says a name twice writes it once. Checked against
    `memory.people` by the caller before writing — this only proposes, it
    never knows what is already on file.
    """
    found: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(relation: str, name: str) -> None:
        normalized = _normalize_name(name)
        key = normalized.lower()
        if key in seen:
            return
        seen.add(key)
        found.append((relation.lower(), normalized))

    for match in _RE_PERSON_FORWARD.finditer(text):
        add(match.group(1), match.group(2))
    for match in _RE_PERSON_ARTICLE.finditer(text):
        add(match.group(1), match.group(2))
    for match in _RE_PERSON_REVERSE.finditer(text):
        add(match.group(2), match.group(1))

    return found[:_MAX_PEOPLE_PER_TURN]


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
            people = _extract_people(raw)
            if people:
                extracted["people"] = [
                    {"name": name, "relation": relation} for relation, name in people
                ]
                # The single-person keys stay for the journaling prompt and
                # any consumer written against the old shape; `people` is
                # the complete list.
                extracted["person_relation"] = people[0][0]
                extracted["person_name"] = people[0][1]

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
