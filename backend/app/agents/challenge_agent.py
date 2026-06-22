"""
Challenge Agent
===============
Socratic CBT-style questioning. Gated by trust and stability.
Only runs when trust_level >= 0.6, emotional_stability >= 0.5,
and the user is NOT in crisis.
Uses Groq 8B (max 80 tokens — one question).
"""

from __future__ import annotations

from app.agents.base_agent import AgentContext, AgentOutput, BaseAgent
from app.agents.groq_client import get_groq_client


class ChallengeAgent(BaseAgent):
    """
    Asks gentle, curious questions that invite the user to examine
    their automatic thoughts — never confrontational, always respectful.
    """

    def __init__(self) -> None:
        super().__init__(
            name="challenge",
            description="Gentle Socratic questioning to examine thoughts",
            llm_tier="8B",
            max_tokens=100,
            always_runs=False,
        )

    async def run(self, ctx: AgentContext) -> AgentOutput:
        """Generate a single Socratic question."""
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
        rag_context = ""
        if ctx.rag_chunks:
            rag_context = (
                "\nRELEVANT THERAPY KNOWLEDGE:\n"
                + "\n---\n".join(ctx.rag_chunks[:3])
                + "\n---\n"
            )
        return (
            f"You are the Challenge Agent of MindLens.\n"
            f"Your role: {self.description}\n"
            f"User's name: {ctx.user_name}\n"
            f"Core emotion: {ctx.eos.core_emotion or 'unknown'}\n"
            f"Trust level: {ctx.eos.trust_level:.2f}\n"
            f"{rag_context}"
            "\nINSTRUCTIONS:\n"
            "1. Ask ONE gentle, curious question.\n"
            "2. Invite the user to examine their thought, not attack it.\n"
            "3. Examples: 'What evidence do you have that thought is true?' or 'If a friend said this, what would you tell them?'\n"
            "4. Never be confrontational. Use their name.\n"
            "5. One sentence only.\n"
            "6. Never diagnose.\n"
        )

    def _build_user_prompt(self, ctx: AgentContext) -> str:
        return f"User said: {ctx.user_text}"
