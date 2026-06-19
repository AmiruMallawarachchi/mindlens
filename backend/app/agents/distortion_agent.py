"""
Distortion Agent
================
Identifies cognitive distortions and guides the user through
a CBT thought record. Runs when modality is CBT.
Uses Groq 8B (max 120 tokens).
"""

from __future__ import annotations

from app.agents.base_agent import AgentContext, AgentOutput, BaseAgent
from app.agents.groq_client import get_groq_client


class DistortionAgent(BaseAgent):
    """
    Helps the user recognise distorted thinking patterns
    (all-or-nothing, catastrophising, mind-reading, etc.)
    and guides a simple thought record.
    """

    def __init__(self) -> None:
        super().__init__(
            name="distortion",
            description="Identify cognitive distortions and guide CBT thought records",
            llm_tier="8B",
            max_tokens=150,
            always_runs=False,
        )

    async def run(self, ctx: AgentContext) -> AgentOutput:
        """Generate a distortion-aware response."""
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
            f"You are the Distortion Agent of MindLens.\n"
            f"Your role: {self.description}\n"
            f"User's name: {ctx.user_name}\n"
            f"Core emotion: {ctx.eos.core_emotion or 'unknown'}\n"
            f"Active modality: {ctx.eos.modality.value}\n"
            "\nINSTRUCTIONS:\n"
            "1. If the user's statement contains a clear cognitive distortion, name it gently.\n"
            "2. Examples of distortions: all-or-nothing, catastrophising, mind-reading, overgeneralisation, personalisation.\n"
            "3. Then ask one thought-record question: 'What is the evidence for and against this thought?'\n"
            "4. Keep it brief — 2-3 sentences max.\n"
            "5. Never diagnose. Never say 'you have' a condition.\n"
            "6. Use their name.\n"
        )

    def _build_user_prompt(self, ctx: AgentContext) -> str:
        return f"User said: {ctx.user_text}"
