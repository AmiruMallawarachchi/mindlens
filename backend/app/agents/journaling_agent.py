"""
Journaling Agent
==================
Generates 3 reflective questions for the user to journal about.
Runs when emotional stability >= 0.3 and mental_fatigue < 0.8.
Uses Groq 8B (max 120 tokens).
"""

from __future__ import annotations

from app.agents.base_agent import AgentContext, AgentOutput, BaseAgent
from app.agents.groq_client import get_groq_client


class JournalingAgent(BaseAgent):
    """
    Provides gentle journaling prompts that help the user
    process emotions and notice patterns.
    """

    def __init__(self) -> None:
        super().__init__(
            name="journaling",
            description="Provide 3 reflective journaling questions",
            llm_tier="8B",
            max_tokens=150,
            always_runs=False,
        )

    async def run(self, ctx: AgentContext) -> AgentOutput:
        """Generate 3 journaling questions."""
        system = self._build_system_prompt(ctx)
        user = self._build_user_prompt(ctx)

        client = get_groq_client()
        result = await client.chat(
            system_prompt=system,
            user_prompt=user,
            model_tier=self.llm_tier,
            max_tokens=self.max_tokens,
            temperature=0.7,
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
            f"You are the Journaling Agent of MindLens.\n"
            f"Your role: {self.description}\n"
            f"User's name: {ctx.user_name}\n"
            f"Core emotion: {ctx.eos.core_emotion or 'unknown'}\n"
            f"Receptiveness to journaling: {ctx.eos.receptiveness.journaling:.2f}\n"
            "\nINSTRUCTIONS:\n"
            "1. Write exactly 3 reflective questions.\n"
            "2. Each question should be one sentence.\n"
            "3. Use their name in the first line.\n"
            "4. Make them feel open, not like homework.\n"
            "5. Example: 'What emotion showed up most today?'\n"
            "6. Never diagnose.\n"
        )

    def _build_user_prompt(self, ctx: AgentContext) -> str:
        return f"User said: {ctx.user_text}"
