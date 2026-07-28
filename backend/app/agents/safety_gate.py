"""Deterministic crisis screening that runs before all model inference.

The orchestrator follows this high-recall regex screen with the isolated crisis
classifier. Either trigger enters crisis mode without calling a generative model.
"""

import re
from typing import Any  # noqa: UP035

from pydantic import BaseModel


class SafetyGateResult(BaseModel):
    """Result of safety gate evaluation."""

    is_crisis: bool
    layer_triggered: str | None = None  # "regex" | "classifier"
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
        Build 40+ regex patterns for crisis detection.

        Covers casual, formal, coded language.
        """
        # Direct self-harm/suicide indicators
        direct_patterns = [
            r"\bkill\s+(myself|me)\b",
            r"\bsuicide\b",
            r"\bsuicid",
            r"\bend\s+(my\s+)?life\b",
            r"\bdon't\s+want\s+to\s+live\b",
            r"\bdone\s+with\s+(this\s+)?life\b",
            r"\bno\s+reason\s+to\s+live\b",
            r"\bwish\s+i\s+was\s+dead\b",
            r"\bhow\s+to\s+(end|kill)\b",
            r"\bcut\s+(myself|my\s+wrists?)\b",
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

        # Hopelessness / Worthlessness
        hopelessness = [
            r"\b(completely\s+)?hopeless\b",
            r"\bno\s+hope\s+left\b",
            r"\bworthless\b",
            # First-person only. "the financial burden on my family" is not a
            # risk indicator; "I'm a burden to my family" is.
            r"\b(i'm|i\s+am|am\s+i)\s+(such\s+)?a\s+burden\b",
            r"\beveryone\s+would\s+be\s+better\s+off\b",
            r"\bnobody\s+cares\b",
            r"\bno\s+one\s+loves\s+me\b",
            r"\bcompletely\s+alone\b",
            r"\bunlovable\b",
            r"\bdefective\b",
        ]

        # Coded/indirect language (common on social media)
        coded = [
            r"\b(bye|goodbye|see\s+you|take\s+care)\s+(forever|soon)\b",
            r"\b(not\s+gonna\s+be\s+around|won't\s+be\s+here)\b",
            r"\b(final|last)\s+message\b",
            r"\brest\s+in\s+peace\b",
            r"\b(this\s+)?(is\s+)?goodbye\b",
            r"\bstop\s+the\s+pain\b",
            r"\bcan't\s+handle\s+this\b",
            r"\bbroken\s+beyond\s+repair\b",
            r"\bcan't\s+escape\b",
        ]

        # Crisis-related substances/methods
        methods = [
            r"\bnoose\b",
            r"\brope\s+(around|to\s+hang)\b",
            r"\bend\s+of\s+my\s+rope\b",
            r"\bpills?\b.*\b(overdose|swallow)\b",
            r"\bgas\b.*\b(chamber|oven)\b",
            r"\bcar.*exhaust\b",
            r"\bbottle.*bleach\b",
            # Order-independent: the original only matched noun-before-verb,
            # so "jump off the bridge" — the more natural phrasing — missed.
            r"\b(train|bridge|cliff|roof|building)\b.*\b(jump|fall)\b",
            r"\b(jump|throw\s+myself)\s+(off|in\s+front\s+of)\b",
        ]

        # Compile all patterns (case-insensitive)
        all_patterns = (
            direct_patterns
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
CRISIS_TEMPLATES = {
    "moderate": "I can hear how much pain you're in right now. You're not alone, and there are people trained to help. Please contact Sri Lanka's National Mental Health Helpline at 1926.",
    "severe": "What you're describing sounds incredibly serious. Your safety is the most important thing right now. Please call NIMH Sri Lanka immediately at 1926, or dial 119 for emergency. You deserve support, and these are real people trained for exactly this.",
}
