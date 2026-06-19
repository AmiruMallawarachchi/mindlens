"""
Routine Agent
=============
Helps users build small, structured daily routines.
Runs when mental_fatigue >= 0.7 or user is receptive to routine.
Uses Groq 8B (max 400 tokens for structured plans).
"""

from __future__ import annotations

from app.agents.base_agent import AgentContext, AgentOutput, BaseAgent
from app.agents.groq_client import get_groq_client


class RoutineAgent(BaseAgent):
    """
    Suggests tiny, achievable routines (morning, evening, or
    mid-day) tailored to the user's current energy and goals.
    """

    def __init__(self) -> None:
        super().__init__(
            name="routine",
            description="Build small, structured daily routines",
            llm_tier="8B",
            max_tokens=350,
            always_runs=False,
        )

    async def run(self, ctx: AgentContext) -> AgentOutput:
        """Generate a micro-routine suggestion."""
        system = self._build_system_prompt(ctx)
        user = self._build_user_prompt(ctx)

        client = get_groq_client()
        result = await client.chat(
            system_prompt=system,
            user_prompt=user,
            model_tier=self.llm_tier,
            max_tokens=self.max_tokens,
            temperature=0.6,
        )

        return AgentOutput(
            agent_name=self.name,
            text=result.text,
            metadata={
                "llm_tier": self.llm_tier,
                "tokens_used": result.tokens_used,
                "latency_ms": result.latency_ms,
            },
        )

    def _build_system_prompt(self, ctx: AgentContext) -> str:
        return (
            f"You are the Routine Agent of MindLens.\n"
            f"Your role: {self.description}\n"
            f"User's name: {ctx.user_name}\n"
            f"Mental fatigue: {ctx.eos.mental_fatigue:.2f}\n"
            f"Receptiveness to routine: {ctx.eos.receptiveness.routine:.2f}\n"
            f"Receptiveness to practical: {ctx.eos.receptiveness.practical:.2f}\n"
            "\nINSTRUCTIONS:\n"
            "1. Suggest ONE tiny routine (2-3 steps max).\n"
            "2. Make it so small it feels almost too easy.\n"
            "3. Format as a simple numbered list.\n"
            "4. Example: '1. Drink water. 2. Step outside for 2 minutes.'\n"
            "5. Use their name. Keep it encouraging, not demanding.\n"
            "6. Never diagnose.\n"
        )

    def _build_user_prompt(self, ctx: AgentContext) -> str:
        return f"User said: {ctx.user_text}"
