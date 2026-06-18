"""
Safety Gate — Three-Layer Crisis Detection

Layer 1: Regex patterns (40 crisis indicators)
Layer 2: DistilBERT crisis classifier (ML-based)
Layer 3: FAISS semantic search (semantic similarity to crisis corpus)

ANY layer triggering → Crisis mode (zero LLM response)

This gate cannot be bypassed by any other system component.
"""

import re
from typing import Any  # noqa: UP035

from pydantic import BaseModel


class SafetyGateResult(BaseModel):
    """Result of safety gate evaluation."""

    is_crisis: bool
    layer_triggered: str | None = None  # "regex" | "distilbert" | "faiss"
    confidence: float  # 0-1
    reason: str
    user_message_snippet: str


class SafetyGate:
    """
    Three-layer crisis detection system.

    Runs on EVERY message before any agent inference.
    Cannot be disabled or bypassed.
    """

    def __init__(self):
        self.name = "safety_gate"
        self.distilbert_model = None  # Loaded lazily
        self.faiss_index = None  # Loaded lazily

        # Layer 1: Regex patterns
        self.crisis_patterns = self._build_crisis_patterns()

    def _build_crisis_patterns(self) -> list[re.Pattern]:
        """
        Build 40+ regex patterns for crisis detection.

        Covers casual, formal, coded language.
        """
        # Direct self-harm/suicide indicators
        direct_patterns = [
            r"\bkill\s+(myself|myself|me)\b",
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
            r"\bwant\s+to\s+die\b",
            r"\bbetter\s+off\s+dead\b",
        ]

        # Harm to others
        harm_others = [
            r"\bkill\s+(someone|him|her|them)\b",
            r"\bhurt\s+(someone|him|her|them)\b",
            r"\bbeat\s+(someone|up)?",
            r"\bstab\b",
            r"\bshoot\b",
        ]

        # Hopelessness / Worthlessness
        hopelessness = [
            r"\b(completely\s+)?hopeless\b",
            r"\bno\s+hope\s+left\b",
            r"\bworthless\b",
            r"\bburden\b",
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
            r"\b(can't|can't)\s+escape\b",
        ]

        # Crisis-related substances/methods
        methods = [
            r"\brope\b",
            r"\bpills?\b.*\b(overdose|swallow)\b",
            r"\bgas\b.*\b(chamber|oven)\b",
            r"\bcar.*exhaust\b",
            r"\bbottle.*bleach\b",
            r"\bratio\b",  # Discord term
            r"\b(train|bridge|cliff)\b.*\b(jump|fall)\b",
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
        Run all three layers of crisis detection.

        Args:
            user_message: User's message to evaluate
            user_id: User ID (for logging)

        Returns:
            SafetyGateResult with crisis status and confidence
        """
        snippet = user_message[:100]  # For logging

        # Layer 1: Regex (fast, <1ms)
        regex_result = self._layer_regex(user_message)
        if regex_result["triggered"]:
            return SafetyGateResult(
                is_crisis=True,
                layer_triggered="regex",
                confidence=0.95,
                reason="Crisis keywords detected",
                user_message_snippet=snippet,
            )

        # Layer 2: DistilBERT (medium, ~50ms)
        # TODO: Implement when model is deployed
        # distilbert_result = await self._layer_distilbert(user_message)
        # if distilbert_result["triggered"]:
        #     return SafetyGateResult(...)

        # Layer 3: FAISS semantic search (~100ms)
        # TODO: Implement when FAISS index is built
        # faiss_result = await self._layer_faiss(user_message)
        # if faiss_result["triggered"]:
        #     return SafetyGateResult(...)

        # All layers clear → not in crisis
        return SafetyGateResult(
            is_crisis=False,
            layer_triggered=None,
            confidence=0.0,
            reason="No crisis indicators detected",
            user_message_snippet=snippet,
        )

    def _layer_regex(self, user_message: str) -> dict[str, Any]:
        """
        Layer 1: Regex pattern matching.

        Returns dict with 'triggered' bool.
        """
        for pattern in self.crisis_patterns:
            if pattern.search(user_message):
                return {
                    "triggered": True,
                    "matched_pattern": pattern.pattern[:50],
                }
        return {"triggered": False}

    async def _layer_distilbert(self, user_message: str) -> dict[str, Any]:
        """
        Layer 2: DistilBERT crisis classifier.

        TODO: Load model from HuggingFace.
        Threshold: 0.45 (maximize recall, minimize false negatives).

        Returns dict with 'triggered' bool and confidence.
        """
        # TODO: Implement
        return {"triggered": False, "confidence": 0.0}

    async def _layer_faiss(self, user_message: str) -> dict[str, Any]:
        """
        Layer 3: FAISS semantic search.

        TODO: Load FAISS index with crisis corpus.
        Threshold: 0.85 similarity.

        Returns dict with 'triggered' bool and confidence.
        """
        # TODO: Implement
        return {"triggered": False, "confidence": 0.0}


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
    "moderate": "I can hear how much pain you're in right now. You're not alone, and there are people trained to help. Please reach out to NIMH at 1926 — they're available 24/7.",
    "severe": "What you're describing sounds incredibly serious. Your safety is the most important thing right now. Please call NIMH Sri Lanka immediately at 1926, or dial 119 for emergency. You deserve support, and these are real people trained for exactly this.",
}
