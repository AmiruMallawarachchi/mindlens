"""
Check-In Agent
================
Proactive follow-up messages sent between sessions.
Runs as a scheduled background job via APScheduler.
Uses Groq 8B (max 80 tokens — 2-3 sentences).
"""

from __future__ import annotations

from app.agents.base_agent import AgentContext, AgentOutput, BaseAgent
from app.agents.groq_client import get_groq_client


class CheckInAgent(BaseAgent):
    """
    Generates gentle, personalised check-in messages
    to maintain continuity between sessions.
    """

    def __init__(self) -> None:
        super().__init__(
            name="checkin",
            description="Generate proactive check-in messages between sessions",
            llm_tier="8B",
            max_tokens=100,
            always_runs=False,
        )

    async def run(self, ctx: AgentContext) -> AgentOutput:
        """Generate a check-in message."""
        system = self._build_system_prompt(ctx)
        user = self._build_user_prompt(ctx)

        client = get_groq_client()
        result = await client.chat(
            system_prompt=system,
            user_prompt=user,
            model_tier=self.llm_tier,
            max_tokens=self.max_tokens,
            temperature=0.75,
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
            f"You are the Check-In Agent of MindLens.\n"
            f"Your role: {self.description}\n"
            f"User's name: {ctx.user_name}\n"
            f"Last known emotion: {ctx.eos.surface_emotion}\n"
            "\nINSTRUCTIONS:\n"
            "1. Write a gentle, warm check-in message (2-3 sentences).\n"
            "2. Use their name.\n"
            "3. No pressure — just a friendly pause.\n"
            "4. Example: 'Hey {name}, just checking in. How are you feeling today?'\n"
            "5. Never diagnose.\n"
        )

    def _build_user_prompt(self, ctx: AgentContext) -> str:
        return f"User's last known state: {ctx.eos.surface_emotion} (distress: {ctx.eos.distress_level:.2f})"
