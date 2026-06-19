"""
Response Assembler
================
Combines outputs from multiple agents into a single coherent response.
Enforces ordering, adds the mandatory disclaimer, and appends
NIMH resources when in crisis mode.
"""

from __future__ import annotations

from app.agents.base_agent import AgentOutput
from app.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Ordering rules: agents appear in this priority sequence
# ---------------------------------------------------------------------------

AGENT_PRIORITY: dict[str, int] = {
    "crisis": 0,        # Always first (or exclusive)
    "empathy": 1,       # Always present
    "mindfulness": 2,   # Grounding before challenge
    "reflection": 3,    # Summarise before challenging
    "distortion": 4,    # CBT thought record
    "challenge": 5,     # Socratic question
    "routine": 6,       # Action plan
    "journaling": 7,    # Reflection prompts
    "music": 8,         # Music therapy
    "checkin": 9,       # Proactive follow-up
    "progress": 10,     # Weekly insight
    "personality": 11,  # Tone adaptation (invisible)
}

# Mandatory disclaimer appended to every response
MANDATORY_DISCLAIMER = (
    "\n\n— MindLens is not a clinical service. "
    "If you need urgent help, please contact NIMH Sri Lanka at 1926."
)

# Crisis-specific resources (always included in crisis mode)
CRISIS_RESOURCES = (
    "\n\n🚨 URGENT SUPPORT:\n"
    "• NIMH Sri Lanka (24/7): 1926\n"
    "• Suicide Prevention Line: 1333\n"
    "• Emergency: 119\n"
    "\nYou are not alone. These are real people trained to help."
)


class ResponseAssembler:
    """
    Stateless assembler. Thread-safe.
    """

    def assemble(
        self,
        outputs: list[AgentOutput],
        *,
        in_crisis: bool = False,
        user_name: str = "friend",
    ) -> str:
        """
        Combine agent outputs into a single user-facing response.

        Args:
            outputs: List of AgentOutput from all invoked agents.
            in_crisis: If True, prepend crisis resources and skip non-crisis agents.
            user_name: Used for personalisation in final text.

        Returns:
            A single string ready to send to the user.
        """
        if not outputs:
            return self._fallback_response(user_name)

        # Crisis mode: ONLY crisis agent output is used
        if in_crisis:
            crisis_output = next(
                (o for o in outputs if o.agent_name == "crisis"), None
            )
            if crisis_output:
                text = crisis_output.text
            else:
                text = self._fallback_crisis_response()
            return text + CRISIS_RESOURCES

        # Normal mode: sort by priority, concatenate with line breaks
        sorted_outputs = sorted(
            outputs,
            key=lambda o: AGENT_PRIORITY.get(o.agent_name, 99),
        )

        parts: list[str] = []
        for output in sorted_outputs:
            if output.text and output.text.strip():
                parts.append(output.text.strip())

        # Deduplicate exact duplicate sentences
        unique_parts = []
        seen = set()
        for part in parts:
            # Normalise for dedup
            normalised = part.lower().strip()
            if normalised not in seen:
                seen.add(normalised)
                unique_parts.append(part)

        text = "\n\n".join(unique_parts)

        # Add disclaimer
        text = text + MANDATORY_DISCLAIMER

        return text

    def _fallback_response(self, user_name: str) -> str:
        """If no agents produced output, return a safe fallback."""
        return (
            f"I'm here with you, {user_name}. Tell me more."
            + MANDATORY_DISCLAIMER
        )

    def _fallback_crisis_response(self) -> str:
        """If crisis agent failed, use a hardcoded safe template."""
        return (
            "I can hear how much pain you're in right now. "
            "You're not alone, and there are people trained to help. "
            "Please reach out to NIMH at 1926 — they're available 24/7."
        )


# Module-level singleton
_default_assembler = ResponseAssembler()


def assemble(
    outputs: list[AgentOutput],
    *,
    in_crisis: bool = False,
    user_name: str = "friend",
) -> str:
    """One-shot assemble using the default instance."""
    return _default_assembler.assemble(outputs, in_crisis=in_crisis, user_name=user_name)
