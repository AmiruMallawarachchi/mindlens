"""
Personality Agent
=================
Adapts tone based on user personality (introvert/extrovert),
attachment style, and age group. Runs invisibly — its output
modifies the prompt context for other agents, not the user directly.
Uses Groq 8B (max 100 tokens).
"""

from __future__ import annotations

from app.agents.base_agent import AgentContext, AgentOutput, BaseAgent
from app.agents.groq_client import get_groq_client


class PersonalityAgent(BaseAgent):
    """
    Analyses the user's communication style and produces a
    'tone directive' that other agents consume.
    """

    def __init__(self) -> None:
        super().__init__(
            name="personality",
            description="Adapt tone and style based on user personality",
            llm_tier="8B",
            max_tokens=100,
            always_runs=False,
        )

    async def run(self, ctx: AgentContext) -> AgentOutput:
        """Generate a tone directive for other agents."""
        system = self._build_system_prompt(ctx)
        user = self._build_user_prompt(ctx)

        client = get_groq_client()
        result = await client.chat(
            system_prompt=system,
            user_prompt=user,
            model_tier=self.llm_tier,
            max_tokens=self.max_tokens,
            temperature=0.5,
        )

        return AgentOutput(
            agent_name=self.name,
            text=result.text,
            metadata={
                "llm_tier": self.llm_tier,
                "tokens_used": result.tokens_used,
                "latency_ms": result.latency_ms,
                "tone_directive": True,
            },
        )

    def _build_system_prompt(self, ctx: AgentContext) -> str:
        age_group = ctx.eos.age_group.value
        attachment = ctx.eos.attachment_style
        social_energy = ctx.eos.social_energy

        tone = "warm and gentle"
        if social_energy < 0.4:
            tone = "quiet, respectful, and spacious"
        elif social_energy > 0.7:
            tone = "energetic, upbeat, and encouraging"

        if attachment == "anxious":
            tone += "; reassuring and consistent"
        elif attachment == "avoidant":
            tone += "; non-intrusive and autonomy-respecting"

        return (
            f"You are the Personality Agent of MindLens.\n"
            f"Your role: {self.description}\n"
            f"User's age group: {age_group}\n"
            f"Attachment style: {attachment}\n"
            f"Social energy: {social_energy:.2f}\n"
            "\nINSTRUCTIONS:\n"
            "1. Write a ONE-SENTENCE tone directive for other agents.\n"
            f"2. The tone should be: {tone}.\n"
            "3. Example: 'Use a quiet, non-intrusive tone; respect their space.'\n"
            "4. Never diagnose.\n"
        )

    def _build_user_prompt(self, ctx: AgentContext) -> str:
        return f"User said: {ctx.user_text}"
