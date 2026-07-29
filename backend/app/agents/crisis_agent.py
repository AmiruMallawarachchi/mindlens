"""
Crisis Agent
============
ZERO LLM — template-only crisis response.
This is the most safety-critical agent in MindLens.

Rules from SYSTEM.md (non-negotiable):
- NEVER calls Groq or any LLM.
- ALWAYS returns templates + NIMH resources.
- ALWAYS includes the NIMH 1926 hotline.
- Session is PAUSED until user confirms they've seen resources.
"""

from __future__ import annotations

from app.agents.base_agent import AgentContext, AgentOutput, BaseAgent
from app.agents.safety_gate import CRISIS_TEMPLATES

# SYSTEM.md §16 mandates NIMH 1926 and Emergency 119 on every crisis response;
# Sumithrayo is a real Sri Lankan crisis line included alongside them. This
# structured list is what the crisis panel renders as contact rows — until
# now nothing populated it, so `resources` was always sent as an empty array
# regardless of `crisis_resources_included: True` in the metadata below.
CRISIS_RESOURCES: list[dict[str, str]] = [
    {"name": "Sri Lanka — Sumithrayo", "number": "011 269 6666"},
    {"name": "National Mental Health Helpline", "number": "1926"},
    {"name": "Emergency services", "number": "119 / 110"},
]


class CrisisAgent(BaseAgent):
    """
    Crisis response agent. Uses pre-written templates only.
    No LLM inference. No model calls. No external dependencies.
    """

    def __init__(self) -> None:
        super().__init__(
            name="crisis",
            description="Emergency crisis response with NIMH resources",
            llm_tier="none",  # NO LLM
            max_tokens=0,     # No generation
            always_runs=False,
        )

    async def run(self, ctx: AgentContext) -> AgentOutput:
        """
        Select appropriate crisis template based on distress level.
        Never makes an external API call.
        """
        distress = ctx.eos.distress_level

        # Select template severity
        if distress >= 0.85:
            template = CRISIS_TEMPLATES["severe"]
        else:
            template = CRISIS_TEMPLATES["moderate"]

        # Personalise with name
        name = ctx.user_name or "friend"
        text = template.replace("{name}", name)

        return AgentOutput(
            agent_name=self.name,
            text=text,
            metadata={
                "llm_tier": "none",
                "template_type": "severe" if distress >= 0.85 else "moderate",
                "crisis_resources_included": True,
                "nimh_number_included": True,
                "resources": CRISIS_RESOURCES,
            },
        )

    def _build_system_prompt(self, ctx: AgentContext) -> str:
        """Crisis agent does not use system prompts."""
        return ""

    def _build_user_prompt(self, ctx: AgentContext) -> str:
        """Crisis agent does not use user prompts."""
        return ""
