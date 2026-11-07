"""Deterministic crisis screening that runs before all model inference.

This is Layer 1 and it is the only screen that can stop a turn before any
model is called. The hosted assessment (Layer 2) can still escalate to crisis
mode afterwards, but it cannot un-trigger this screen — see
app/agents/hosted_graph.py for the node order.
"""

import re
from typing import Any  # noqa: UP035

from pydantic import BaseModel


class SafetyGateResult(BaseModel):
    """Result of safety gate evaluation."""

    is_crisis: bool
    layer_triggered: str | None = None  # "regex" from this gate; the hosted
    # assessment sets "hosted_assessment" itself, in hosted_graph._assess.
    confidence: float  # 0-1
    reason: str
    user_message_snippet: str


class SafetyGate:
    """High-recall deterministic screen that runs before model inference."""

    def __init__(self):
        self.name = "safety_gate"
        self.crisis_patterns = self._build_crisis_patterns()

    def _build_crisis_patterns(self) -> list[re.Pattern]:
        """
        Build the Layer 1 crisis screen.

        Two properties have to hold at once, and they pull against each other:

          RECALL   — a person in crisis writes in ordinary words, not clinical
                     ones. Missing "I want to hurt myself" is the worst failure
                     mode this file can have.
          PRECISION— a false positive replaces the therapy path with a helpline
                     card and zero model calls. Users notice, and it teaches
                     them to ignore the message that matters.

        The rule the patterns follow: *an object or a subject decides it.*
        "worthless" alone is not a risk signal — a meeting can be worthless —
        but "I'm worthless" is. "I can't handle this workload" is about a
        workload; "I can't handle this", with nothing after it, is about being
        alive. So ambiguous words are only allowed through when bound to the
        first person, or when the sentence has no object left to be about.
        """
        # Direct self-harm/suicide indicators
        direct_patterns = [
            r"\bkill\s+(myself|me)\b",
            r"\bkill\s+myself\b",
            r"\bkms\b",  # written shorthand for "kill myself"
            r"\bsuicide\b",
            r"\bsuicid",
            r"\bend\s+(my\s+)?life\b",
            r"\bend(s|ing)?\s+it\s+all\b",
            r"\bfinish\s+myself(\s+off)?\b",
            r"\boff\s+myself\b",  # UK shorthand: "I might off myself"
            r"\btake\s+(my\s+)?(own\s+)?life\b",
            r"\bdon't\s+want\s+to\s+live\b",
            r"\b(never\s+wanted|don't\s+want)\s+to\s+be\s+here\b",
            r"\bdone\s+with\s+(this\s+)?life\b",
            r"\bno\s+reason\s+to\s+live\b",
            r"\bno\s+reason\s+to\s+(go\s+on|carry\s+on)\b",
            r"\bn't\s+worth\s+(being\s+alive|living|my\s+life)\b",
            r"\blife\s+isn'?t\s+worth\s+(living|it)\b",
            r"\bwish\s+i\s+(was|were)\s+dead\b",
            r"\bwish\s+i\s+hadn'?t\s+woken\s+(up\s+)?(this\s+morning\s+)?\b",
            r"\bwake\s+up\s+dead\b",
            r"\bhow\s+to\s+(end|kill)\b",
            r"\bcut\s+(myself|my\s+wrists?)\b",
            r"\bcutting\s+myself\b",
            r"\bslash\s+(myself|my\s+wrists?)\b",
            r"\bhang\s+myself\b",
            r"\boverdose\b",
            r"\bgive\s+up\b.*\b(life|everything)\b",
            r"\bcan't\s+do\s+this\s+anymore\b",
            # Restored from the pre-merge gate, which the production branch
            # had dropped. Both are high-frequency crisis phrasings.
            r"\bcan't\s+go\s+on\b",
            r"\bgoodbye\s+forever\b",
            r"\bwant\s+to\s+die\b",
            r"\bbetter\s+off\s+dead\b",
            r"\b(no|not)\s+point\s+(in\s+)?(me\s+)?(being\s+here|me\s+here|this)\b",
            r"\bwithout\s+me\s+everyone\b",
        ]

        # "hurt myself" is the single most common casual phrasing of
        # self-harm and the old screen had no pattern for it at all.
        self_harm_patterns = [
            r"\bhurt(ing)?\s+myself\b",
            r"\bharming\s+myself\b",
            r"\bmake\s+(myself|me)\s+(sick|hurt)\b.*\bon\s+purpose\b",
            r"\b(hurt|harm)\s+(me|myself)\s+(on\s+purpose|deliberately)\b",
            r"\bself[-\s]?harm(ing|ed)?\b",
        ]

        # Harm to others
        # Each verb REQUIRES an object. A bare verb is ordinary English:
        # "I beat my personal best", "shoot, I forgot", "a stabbing pain".
        harm_others = [
            r"\bkill\s+(someone|him|her|them)\b",
            r"\bhurt\s+(someone|him|her|them)\b",
            r"\bbeat\s+(someone|him|her|them)\s+up\b",
            r"\bbeat\s+up\s+(someone|him|her|them)\b",
            r"\bstab\s+(someone|him|her|them|myself)\b",
            r"\bshoot\s+(someone|him|her|them|myself|up\s+the)\b",
        ]

        # Hopelessness / worthlessness.
        # Bound to the first person on purpose. "That meeting was completely
        # worthless" is a judgement about a meeting; "I'm worthless" — and
        # even "I feel worthless as a programmer" — is a person describing
        # themselves, and the gate takes that at face value. Deliberately
        # recall-leaning: the cost of a false positive here is a helpline card
        # the user can talk past; the cost of the opposite choice is a missed
        # attempt.
        hopelessness = [
            # "hopeless" about a project or a match report is situational
            # pessimism; "hopeless" attached to the self, to everything, or to
            # life is the clinical indicator. The noun is unbound — nobody
            # writes "a sense of hopelessness" about a spreadsheet.
            r"\b(i'?m|i\s+am|i\s+feel|i\s+felt|feeling|everything\s+feels?|it\s+all\s+feels?|life\s+(is|feels?)|there'?s\s+no)\s+(so\s+|completely\s+|totally\s+|utterly\s+|absolutely\s+)?hopeless\b",
            r"\bhopelessness\b",
            r"\bno\s+hope\s+left\b",
            r"\b(i'?m|i\s+am|am\s+i|feel|feeling)\s+(so\s+|very\s+|completely\s+|totally\s+|utterly\s+)?worthless\b",
            r"\bmy\s+(life|existence|presence)\s+(is\s+)?(worthless|pointless|meaningless)\b",
            # First-person only. "the financial burden on my family" is not a
            # risk indicator; "I'm a burden to my family" is.
            r"\b(i'm|i\s+am|am\s+i)\s+(such\s+)?a\s+burden\b",
            r"\beveryone\s+would\s+be\s+better\s+off\b",
            r"\b(nobody|no\s+one)\s+cares\s+(about\s+me|if\s+i\s+(die|am\s+gone|wasn'?t\s+here)|whether\s+i\s+(live|die))\b",
            r"\bno\s+one\s+loves\s+me\b",
            r"\b(i'?m|i\s+am|i\s+feel|feel\s+i\s+am)\s+(so\s+|very\s+|completely\s+|totally\s+|utterly\s+)?(alone|isolated)\b",
            r"\bunlovable\b",
            r"\bdefective\b",
            r"\bi\s+don'?t\s+care\s+if\s+i\s+(live|die|am\s+alive)\b",
            r"\b(i\s+)?(stopped|quit)\s+caring\s+(about\s+)?(myself|living|being\s+here)\b",
        ]

        # Coded/indirect language (common on social media)
        coded = [
            r"\b(bye|goodbye|see\s+you|take\s+care)\s+(forever|soon)\b",
            r"\b(not\s+gonna\s+be\s+around|won't\s+be\s+here)\b",
            r"\b(final|last)\s+message\b",
            r"\brest\s+in\s+peace\b",
            # "goodbye" on its own is how every email ends. It counts only as
            # the last word of a message, or when a farewell is finalised
            # ("this is my last goodbye", "goodbye to everyone").
            r"\bgoodbye\b[\s.,!?]*$",
            r"\bthis\s+is\s+my\s+(last|final)\b",
            r"\bgoodbye\s+to\s+(everyone|you\s+all|all\s+of\s+you)\b",
            r"\bstop\s+the\s+pain\b",
            # Objectless by design: "I can't handle this workload" is about a
            # workload. Ending the sentence on "this" is what the cry sounds
            # like. "anymore" makes it explicit either way.
            r"\bcan'?t\s+handle\s+(this|it)(\s+(anymore|any\s+more))?\s*[.!?]*\s*$",
            r"\bcan'?t\s+handle\s+(being\s+here|living|my\s+life|this\s+life)\b",
            r"\bbroken\s+beyond\s+repair\b",
            r"\bcan't\s+escape\b",
        ]

        # Crisis-related substances/methods
        methods = [
            r"\bnoose\b",
            r"\brope\s+(around|to\s+hang)\b",
            r"\bend\s+of\s+my\s+rope\b",
            r"\bpills?\b.*\b(overdose|swallow)\b",
            # "I forgot to take my pills" is a medication, not an attempt.
            # The quantity word is what distinguishes the two.
            r"\b(swallow(ed|s|ing)?|took|taking|ate|eat)\s+(a\s+|the\s+)?(whole\s+|entire\s+|full\s+)?(bottle|packet|pack|handful|fistful|strip|blister)s?\s+of\s+(pills?|tablets?|meds?)\b",
            r"\bgas\b.*\b(chamber|oven)\b",
            r"\bcar.*exhaust\b",
            r"\bbottle.*bleach\b",
            r"\bgun\s+to\s+my\s+(head)\b",
            r"\bput\s+(a\s+)?(gun|knife)\s+to\b",
            # Order-independent: the original only matched noun-before-verb,
            # so "jump off the bridge" — the more natural phrasing — missed.
            r"\b(train|bridge|cliff|roof|building)\b.*\b(jump|fall)\b",
            r"\b(jump|throw\s+myself)\s+(off|in\s+front\s+of)\b",
        ]

        # Compile all patterns (case-insensitive)
        all_patterns = (
            direct_patterns
            + self_harm_patterns
            + harm_others
            + hopelessness
            + coded
            + methods
        )
        return [re.compile(pattern, re.IGNORECASE) for pattern in all_patterns]

    async def evaluate(
        self,
        user_message: str,
        user_id: str | None = None,
    ) -> SafetyGateResult:
        """
        Run deterministic crisis screening.

        Args:
            user_message: User's message to evaluate
            user_id: User ID (for logging)

        Returns:
            SafetyGateResult with crisis status and confidence
        """
        snippet = user_message[:100]  # For logging

        # Regex screening is intentionally first and independent of model health.
        regex_result = self._layer_regex(user_message)
        if regex_result["triggered"]:
            return SafetyGateResult(
                is_crisis=True,
                layer_triggered="regex",
                confidence=0.95,
                reason="Crisis keywords detected",
                user_message_snippet=snippet,
            )

        # The orchestrator runs the classifier after this screen clears.
        return SafetyGateResult(
            is_crisis=False,
            layer_triggered=None,
            confidence=0.0,
            reason="No crisis indicators detected",
            user_message_snippet=snippet,
        )

    @staticmethod
    def _normalize(user_message: str) -> str:
        """
        Fold Unicode punctuation to ASCII before matching.

        Phones and word processors substitute typographic apostrophes
        automatically, so a message typed on any mobile keyboard arrives as
        "I can’t do this anymore". Every pattern here is written with a
        straight apostrophe, so without this fold those messages sail past
        Layer 1 entirely. This is a crisis-recall fix, not cosmetics.
        """
        return (
            user_message.replace("’", "'")  # right single quote
            .replace("‘", "'")  # left single quote
            .replace("ʼ", "'")  # modifier letter apostrophe
            .replace("“", '"')
            .replace("”", '"')
        )

    def _layer_regex(self, user_message: str) -> dict[str, Any]:
        """
        Layer 1: Regex pattern matching.

        Returns dict with 'triggered' bool.
        """
        normalized = self._normalize(user_message)
        for pattern in self.crisis_patterns:
            if pattern.search(normalized):
                return {
                    "triggered": True,
                    "matched_pattern": pattern.pattern[:50],
                }
        return {"triggered": False}

# --- Singleton instance ---
safety_gate = SafetyGate()


# --- Legacy function for compatibility ---
async def layer1_keyword_scan(text: str) -> dict[str, Any]:
    """Legacy wrapper for backward compatibility."""
    result = safety_gate._layer_regex(text)
    return {
        "triggered": result["triggered"],
        "matches": [result.get("matched_pattern", "")],
        "layer": 1,
    }


# Crisis templates (ZERO LLM - as per SYSTEM.md)
# No phone numbers here, on purpose. These strings are shown to anyone, in
# any country, and the old ones named Sri Lanka's helplines regardless of
# where the user actually was. The numbers live in
# app/core/crisis_resources.py, arrive as `metadata.resources`, and are
# chosen per user; the template only points at them.
CRISIS_TEMPLATES = {
    "moderate": (
        "I can hear how much pain you're in right now. You're not alone, and "
        "there are people trained to help — the support lines listed below "
        "are real people, and you can call or text any of them, free, right now."
    ),
    "severe": (
        "What you're describing sounds incredibly serious. Your safety is the "
        "most important thing right now. Please reach out to one of the "
        "services listed below immediately — the first is a crisis line and "
        "the next is your local emergency number. You deserve support, and "
        "these are real people trained for exactly this."
    ),
}
