"""Heuristic extraction of durable facts from one user message.

This is the write behind the Memory page's promise that mentioning a person
or a hard topic makes it show up there. It is deliberately heuristic rather
than an LLM call: its output is replayed into every future prompt, so a bad
write does not cost one turn — it persists and quietly corrupts recall. A
small fixed vocabulary for topics and coping, plus a narrow regex for names,
bounds what can ever be written.

Call this with the *raw* user message. ``anonymize()`` replaces titled or
capitalised names ("Dr Perera" -> "[NAME]") before anything reaches Groq,
which is correct for anything that leaves the process but would make person
extraction impossible. The result stays on the server and only ever becomes
a key in this user's own ``user_memory`` document.
"""

from __future__ import annotations

import re
from typing import Any

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
_NAME = r"[A-Z][a-zA-Z']{1,20}(?:\s+[A-Z][a-zA-Z']{1,20})?"

# The same shape but case-insensitive, for use ONLY after a phrase that has
# already declared a name is coming ("called x", "name is x"). People type
# their own lives in lowercase — "my mums name is rehana" — and refusing to
# store that taught the user they had to capitalise to be heard, which is
# not a rule a wellbeing app gets to impose. Bare adjacency still requires
# the capital: in "my sister said", "said" is a lowercase word directly
# after the relation and is indistinguishable from a lowercase name.
_NAME_ANY_CASE = r"[A-Za-z][a-zA-Z']{1,20}(?:\s+[A-Z][a-zA-Z']{1,20})?"

# Words that follow "called"/"name is" often enough to be worth excluding —
# without these, "my sister called me" stores a person named "me".
_NOT_A_NAME = (
    "me|us|him|her|them|you|it|today|yesterday|tonight|earlier|again|back|"
    "and|but|so|because|when|while|about|after|before|now|just|also"
)

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
_DECLARED = rf"(?:\s+(?:called|named)|'?s?\s+name\s+is)\s+(?!(?i:{_NOT_A_NAME})\b)"

_RE_PERSON_FORWARD = re.compile(
    rf"\b(?i:my\s+({_RELATIONS}))\s*,?\s+({_NAME})\b"
)
# Same, but the name was explicitly declared, so case is not required.
_RE_PERSON_DECLARED = re.compile(
    rf"\b(?i:my\s+({_RELATIONS})){_DECLARED}({_NAME_ANY_CASE})\b"
)

# "I have a boyfriend called Hasanka" — the indefinite article is just as
# common as "my" when someone introduces a person for the first time, which
# is exactly the turn this needs to catch. Restricted to the explicit
# naming connectors: "a friend called Alex" is unambiguous, whereas bare
# adjacency after "a" ("a sister Amaya") is not idiomatic and would only
# widen the false-positive surface for no real gain.
_RE_PERSON_ARTICLE = re.compile(
    rf"\b(?i:an?\s+({_RELATIONS})){_DECLARED}({_NAME_ANY_CASE})\b"
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

# One turn introducing more than a handful of people is far more likely to
# be pasted text or an attempt to bulk-write the graph than a real
# introduction, so the write is bounded rather than unbounded.
_MAX_PEOPLE_PER_TURN = 3


def _normalize_name(name: str) -> str:
    """Title-case each word — so "AMAYA", "amaya" and "Amaya" collapse to
    the same ``people`` key instead of becoming three separate entries.

    Per word, not per string: a single pass over the whole thing turned
    "Dr Perera" into "Dr perera"."""
    return " ".join(w[:1].upper() + w[1:].lower() for w in name.split())


def _extract_people(text: str) -> list[tuple[str, str]]:
    """Return every (relation, name) plausibly introduced in this message.

    Deliberately not just the first: "I have a boyfriend called Hasanka and
    my mum's name is Rehana" is one ordinary sentence introducing two
    people, and returning only one silently dropped the other.

    Order is preserved and names are de-duplicated case-insensitively, so a
    message that says a name twice writes it once. Checked against
    ``memory.people`` by the caller before writing — this only proposes, it
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

    # Declared forms first: "my mum's name is rehana" also matches the
    # bare-adjacency pattern against nothing useful, and running the
    # explicit one first means the lowercase name wins its slot.
    for match in _RE_PERSON_DECLARED.finditer(text):
        add(match.group(1), match.group(2))
    for match in _RE_PERSON_ARTICLE.finditer(text):
        add(match.group(1), match.group(2))
    for match in _RE_PERSON_FORWARD.finditer(text):
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


def extract_memory(
    user_text: str,
    *,
    distress_level: float = 0.0,
    valence: str = "neutral",
    memory_depth: str = "everything",
) -> dict[str, Any]:
    """Return the durable facts this turn should add to ``user_memory``.

    Shape (all keys optional)::

        {"people": [{"name": "Amaya", "relation": "sister"}],
         "person_name": "Amaya", "person_relation": "sister",
         "trigger_topic": "exams", "effective_coping": "going for a walk"}

    ``memory_depth == "nothing"`` returns ``{}``: a user who asked MindLens
    not to draw on memory should not have new memory accumulating in the
    background either.

    ``user_text`` must be the un-anonymised message — see the module
    docstring for why.
    """
    if memory_depth == "nothing":
        return {}

    extracted: dict[str, Any] = {}
    text_lower = user_text.lower()

    people = _extract_people(user_text)
    if people:
        extracted["people"] = [
            {"name": name, "relation": relation} for relation, name in people
        ]
        # The single-person keys stay for the journaling prompt and any
        # consumer written against the old shape; `people` is the complete
        # list.
        extracted["person_relation"] = people[0][0]
        extracted["person_name"] = people[0][1]

    topic = _extract_topic(text_lower, distress_level, valence == "negative")
    if topic:
        extracted["trigger_topic"] = topic

    coping = _extract_coping(text_lower)
    if coping:
        extracted["effective_coping"] = coping

    return extracted
