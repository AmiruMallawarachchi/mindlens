"""
Reflection Agent
================
Summarises what the user said, identifies the emotional core,
and gently reframes the narrative. Runs when session_depth >= 0.3.
Uses Groq 8B (max 50 tokens — one sentence).
"""

from __future__ import annotations

from app.agents.base_agent import AgentContext, AgentOutput, BaseAgent
from app.agents.groq_client import get_groq_client


class ReflectionAgent(BaseAgent):
    """
    Reflects back the user's experience in a concise, validating way.
    Helps them feel heard and often surfaces the core emotion.
    """

    def __init__(self) -> None:
        super().__init__(
            name="reflection",
            description="Summarise and reframe the user's emotional experience",
            llm_tier="8B",
            max_tokens=80,
            always_runs=False,
        )

    async def run(self, ctx: AgentContext) -> AgentOutput:
        """Generate a one-sentence reflection."""
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
            f"You are the Reflection Agent of MindLens.\n"
            f"Your role: {self.description}\n"
            f"User's name: {ctx.user_name}\n"
            f"Core emotion: {ctx.eos.core_emotion or 'unknown'}\n"
            "\nINSTRUCTIONS:\n"
            "1. Write ONE concise sentence that captures the emotional core of what the user said.\n"
            "2. Use their name.\n"
            "3. Be validating but not overly dramatic.\n"
            "4. Example: 'It sounds like you're feeling unseen at work, and that hurts.'\n"
            "5. Never diagnose. Never give advice.\n"
        )

    def _build_user_prompt(self, ctx: AgentContext) -> str:
        return f"User said: {ctx.user_text}"
