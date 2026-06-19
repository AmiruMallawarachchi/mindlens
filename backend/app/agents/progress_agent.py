"""
Progress Agent
==============
Provides weekly insights summarising the user's emotional journey.
Runs at end of session or on weekly trigger.
Uses Groq 8B (max 350 tokens).
"""

from __future__ import annotations

from app.agents.base_agent import AgentContext, AgentOutput, BaseAgent
from app.agents.groq_client import get_groq_client


class ProgressAgent(BaseAgent):
    """
    Summarises trends, celebrates small wins, and gently
    notes patterns across the user's session history.
    """

    def __init__(self) -> None:
        super().__init__(
            name="progress",
            description="Provide weekly emotional insight and trend summary",
            llm_tier="8B",
            max_tokens=350,
            always_runs=False,
        )

    async def run(self, ctx: AgentContext) -> AgentOutput:
        """Generate a progress insight."""
        system = self._build_system_prompt(ctx)
        user = self._build_user_prompt(ctx)

        client = get_groq_client()
        result = await client.chat(
            system_prompt=system,
            user_prompt=user,
            model_tier=self.llm_tier,
            max_tokens=self.max_tokens,
            temperature=0.65,
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
            f"You are the Progress Agent of MindLens.\n"
            f"Your role: {self.description}\n"
            f"User's name: {ctx.user_name}\n"
            f"Current session depth: {ctx.eos.session_depth:.2f}\n"
            f"Alliance score: {ctx.eos.alliance_score:.2f}\n"
            "\nINSTRUCTIONS:\n"
            "1. Summarise what you've noticed about the user's journey so far.\n"
            "2. Celebrate ONE small win.\n"
            "3. Gently note one pattern if it's clear and kind.\n"
            "4. Keep it warm and encouraging — 4-5 sentences.\n"
            "5. Use their name.\n"
            "6. Never diagnose. Never compare to others.\n"
        )

    def _build_user_prompt(self, ctx: AgentContext) -> str:
        # Include session history summary if available
        history_summary = ""
        if ctx.session_history:
            emotions = [turn.get("emotion", "unknown") for turn in ctx.session_history[-5:]]
            history_summary = f"Recent emotions: {', '.join(emotions)}"

        return f"User's current state: {ctx.eos.surface_emotion}. {history_summary}"
