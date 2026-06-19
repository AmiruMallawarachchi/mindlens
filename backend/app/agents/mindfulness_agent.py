"""
Mindfulness Agent
=================
Generates grounding exercises, breathing techniques, and sensory
anchors based on the user's distress level.
Runs when distress > 0.5 or core emotion is anxiety/fear.
Uses Groq 8B (max 250 tokens for structured exercises).
"""

from __future__ import annotations

from app.agents.base_agent import AgentContext, AgentOutput, BaseAgent
from app.agents.groq_client import get_groq_client


class MindfulnessAgent(BaseAgent):
    """
    Delivers evidence-based grounding techniques: 4-7-8 breathing,
    5-4-3-2-1 senses, body scan, progressive muscle relaxation.
    """

    def __init__(self) -> None:
        super().__init__(
            name="mindfulness",
            description="Provide grounding and breathing exercises",
            llm_tier="8B",
            max_tokens=250,
            always_runs=False,
        )

    async def run(self, ctx: AgentContext) -> AgentOutput:
        """Generate a grounding exercise tailored to distress level."""
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
        distress = ctx.eos.distress_level

        if distress >= 0.8:
            technique = (
                "EMERGENCY GROUNDING (severe distress):\n"
                "- 5-4-3-2-1 senses technique (name 5 things you see, 4 you hear, etc.)\n"
                "- Cold water on wrists or ice cube holding\n"
                "- Grounding statement: 'I am here, I am safe, this feeling will pass'"
            )
        elif distress >= 0.6:
            technique = (
                "BOX BREATHING (moderate distress):\n"
                "- Inhale 4 counts, hold 4, exhale 4, hold 4\n"
                "- Repeat 4 cycles\n"
                "- Focus on the square pattern of breath"
            )
        else:
            technique = (
                "4-7-8 RELAXATION BREATH (mild distress):\n"
                "- Inhale 4 counts, hold 7, exhale 8\n"
                "- Gentle belly breathing\n"
                "- Soft ambient sound optional"
            )

        return (
            f"You are the Mindfulness Agent of MindLens.\n"
            f"Your role: {self.description}\n"
            f"User's name: {ctx.user_name}\n"
            f"Distress level: {distress:.2f}\n"
            f"Core emotion: {ctx.eos.core_emotion or 'unknown'}\n"
            f"Receptiveness to breathing: {ctx.eos.receptiveness.breathing:.2f}\n"
            f"Receptiveness to grounding: {ctx.eos.receptiveness.grounding:.2f}\n"
            "\nTECHNIQUE TO USE:\n"
            f"{technique}\n"
            "\nINSTRUCTIONS:\n"
            "1. Guide the user through ONE technique step by step.\n"
            "2. Use their name. Keep instructions clear and numbered.\n"
            "3. Be gentle — no pressure. They can skip any step.\n"
            "4. Aim for 4-6 sentences total.\n"
            "5. Never diagnose.\n"
        )

    def _build_user_prompt(self, ctx: AgentContext) -> str:
        return f"User said: {ctx.user_text}"
