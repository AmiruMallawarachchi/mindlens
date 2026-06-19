"""
Empathy Agent
=============
Warm, validating, non-clinical emotional response.
Always runs on every turn. Uses Groq 8B by default, 70B for high distress.
"""

from __future__ import annotations

from app.agents.base_agent import AgentContext, AgentOutput, BaseAgent
from app.agents.groq_client import get_groq_client


class EmpathyAgent(BaseAgent):
    """
    The first agent every user sees. Validates feelings, reflects emotion,
    and establishes therapeutic alliance. Never diagnoses.
    """

    def __init__(self) -> None:
        super().__init__(
            name="empathy",
            description="Provide warm, validating emotional support",
            llm_tier="8B",
            max_tokens=200,
            always_runs=True,
        )

    async def run(self, ctx: AgentContext) -> AgentOutput:
        """Generate an empathic response."""
        system = self._build_system_prompt(ctx)
        user = self._build_user_prompt(ctx)

        # Use deep model for high distress
        tier = "70B" if ctx.eos.should_use_deep_llm() else "8B"

        client = get_groq_client()
        result = await client.chat(
            system_prompt=system,
            user_prompt=user,
            model_tier=tier,
            max_tokens=self.max_tokens,
            temperature=0.75,
        )

        return AgentOutput(
            agent_name=self.name,
            text=result.text,
            metadata={
                "llm_tier": tier,
                "tokens_used": result.tokens_used,
                "latency_ms": result.latency_ms,
            },
        )

    def _build_system_prompt(self, ctx: AgentContext) -> str:
        return (
            f"You are the Empathy Agent of MindLens.\n"
            f"Your role: {self.description}\n"
            f"User's current emotional state: {ctx.eos.surface_emotion} "
            f"(distress: {ctx.eos.distress_level:.2f})\n"
            f"Core emotion: {ctx.eos.core_emotion or 'unknown'}\n"
            f"Suppressed emotion: {ctx.eos.suppressed_emotion or 'none'}\n"
            f"User's name: {ctx.user_name}\n"
            f"Session depth: {ctx.eos.session_depth:.2f}\n"
            "\nINSTRUCTIONS:\n"
            "1. Validate the user's feeling directly. Use their name.\n"
            "2. Reflect back the emotion you heard.\n"
            "3. Keep it to 2-4 sentences. Warm, not clinical.\n"
            "4. Never diagnose. Never suggest medication.\n"
            "5. End with a gentle open question if appropriate.\n"
        )

    def _build_user_prompt(self, ctx: AgentContext) -> str:
        return f"User said: {ctx.user_text}"
