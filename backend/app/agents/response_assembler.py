"""
Response Assembler
================
Combines outputs from multiple agents into a single coherent response.
Enforces ordering, adds the mandatory disclaimer, and appends
NIMH resources when in crisis mode.
"""

from __future__ import annotations

from app.agents.base_agent import AgentOutput
from app.agents.response_validator import ResponseValidator
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

# Agents whose text already has its own place in the UI. Including it in
# the prose too showed the same sentence twice — music's text is what the
# music card renders as its message.
CARD_RENDERED_AGENTS = frozenset({"music"})

# Empathy opens the turn; at most this many specialists may add to it.
#
# Every speaking agent writes a *complete* conversational turn, so with no
# cap the assembler stapled three or four whole replies together: empathy
# greeting, then a distortion challenge, then a music pitch, in one wall of
# text. It read like a committee rather than one person, and it challenged
# users who had only said they wanted help. The agents still all run —
# their metadata drives the thinking panel — but only this many get to
# speak. Priority order below decides who wins, so grounding beats
# challenging when both fire.
MAX_SPECIALIST_VOICES = 1

# Mandatory disclaimer appended to every response
MANDATORY_DISCLAIMER = (
    "\n\n— MindLens is not a clinical service. "
    "If you need urgent help, please contact NIMH Sri Lanka at 1926."
)

# Crisis-specific resources (always included in crisis mode)
CRISIS_RESOURCES = (
    "\n\n🚨 URGENT SUPPORT:\n"
    "• NIMH National Mental Health Helpline: 1926\n"
    "• Emergency: 119\n"
    "\nYou are not alone. These are real people trained to help."
)


class ResponseAssembler:
    """
    Stateless assembler. Thread-safe.
    """

    def __init__(self) -> None:
        self._validator = ResponseValidator()

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
            return self._validated_or_fallback(
                text + CRISIS_RESOURCES, crisis=True, user_name=user_name
            )

        # Normal mode: sort by priority, concatenate with line breaks
        sorted_outputs = sorted(
            outputs,
            key=lambda o: AGENT_PRIORITY.get(o.agent_name, 99),
        )

        parts: list[str] = []
        specialists_spoken = 0
        for output in sorted_outputs:
            if not (output.text and output.text.strip()):
                continue
            if output.agent_name in CARD_RENDERED_AGENTS:
                continue
            if output.agent_name != "empathy":
                if specialists_spoken >= MAX_SPECIALIST_VOICES:
                    continue
                specialists_spoken += 1
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

        # No disclaimer appended here any more. It is chrome, not something
        # the companion said, and stapling it onto the prose put it mid-reply:
        # "...what's making it hard to get started? - MindLens is not a
        # clinical service. If you need urgent help, contact NIMH..."
        #
        # The UI carries it persistently instead - the sidebar on desktop,
        # and under the composer below 780px where the sidebar is a drawer -
        # so it is still always on screen as DESIGN.md 4.1 requires, just
        # not spoken by the companion.
        #
        # The crisis path is deliberately untouched: there the resources are
        # the message, not decoration around it.

        if not text.strip():
            # Every agent that ran either had nothing to say (a card-only
            # agent like music, or one held back by the specialist cap) or
            # came back with genuinely empty text — a Groq call whose content
            # was "" (a real API hiccup, or every token spent on hidden
            # reasoning; see groq_client's reasoning_effort pin for the class
            # of bug this is). Feeding "" to the validator produced the
            # unhelpful "empty_input" block-and-fallback combination, which
            # then rendered the same fixed line regardless of who was
            # supposed to speak. Naming which agent failed here at least
            # makes the cause diagnosable instead of an unexplained stub.
            empty_speakers = sorted(
                {o.agent_name for o in outputs if o.agent_name not in CARD_RENDERED_AGENTS}
            )
            logger.warning(
                "No agent produced usable text this turn (ran: %s) — using fallback",
                empty_speakers,
            )
            return self._fallback_response(user_name)

        return self._validated_or_fallback(text, crisis=False, user_name=user_name)

    def _validated_or_fallback(
        self, text: str, *, crisis: bool, user_name: str
    ) -> str:
        report = self._validator.validate(text)
        if report.passed:
            return text
        logger.error(
            "Blocked assembled response: categories=%s severity=%s",
            report.blocked_categories,
            report.severity,
        )
        if crisis:
            return self._fallback_crisis_response() + CRISIS_RESOURCES
        return self._fallback_response(user_name)

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
            "Please reach out to the National Mental Health Helpline at 1926."
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
