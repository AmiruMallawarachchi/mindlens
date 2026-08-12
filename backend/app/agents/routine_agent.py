"""
Routine Agent — MindLens v3 SYSTEM.md §5.9
============================================
Trigger: "burnout" in mh_labels OR user explicitly asks.
Uses Groq 70B (needs pattern synthesis). Max 400 tokens.

Purpose: Generate a personalised daily wellness plan.
Rules:
- Reference their specific situation (e.g., "You have exams Sunday")
- Introvert-aware: if introvert_score > 0.6 → solo activities only
- Link sleep (always include 7-hour sleep block)
- Max 6 items per day
"""

from __future__ import annotations

from app.agents.base_agent import AgentContext, AgentOutput, BaseAgent
from app.agents.groq_client import get_groq_client


class RoutineAgent(BaseAgent):
    """
    Generates a personalised daily wellness plan tailored to the
    user's age, schedule, energy level, and preferences.

    Trigger: mental_fatigue >= 0.7 OR user explicitly asks for routine.
             (Note: the orchestrator also routes on burnout keywords.)
    """

    def __init__(self) -> None:
        super().__init__(
            name="routine",
            description="Build small, structured daily routines",
            llm_tier="70B",  # SYSTEM.md: "needs pattern synthesis"
            max_tokens=350,
            always_runs=False,
        )

    def _build_system_prompt(self, ctx: AgentContext) -> str:
        return self._build_system_prompt_v3(ctx)

    def _build_user_prompt(self, ctx: AgentContext) -> str:
        return self._build_user_prompt_v3(ctx)

    async def run(self, ctx: AgentContext) -> AgentOutput:
        """Generate a micro-routine suggestion."""
        system = self._build_system_prompt_v3(ctx)
        user = self._build_user_prompt_v3(ctx)

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
            text=result.text.strip(),
            metadata={
                "llm_tier": self.llm_tier,
                "tokens_used": result.tokens_used,
                "latency_ms": result.latency_ms,
            },
        )

    def _build_system_prompt_v3(self, ctx: AgentContext) -> str:
        """SYSTEM.md §5.9: Personalised, introvert-aware, sleep-linked."""
        name = ctx.user_name or "friend"
        age_group = ctx.eos.age_group.value
        introvert_score = ctx.eos.introvert_score

        # Introvert-aware guidance
        introvert_note = ""
        if introvert_score < 0.4:
            introvert_note = (
                f"- {name} is introvert-leaning (score: {introvert_score:.2f}).\n"
                f"- Include ONLY solo activities. No social obligations.\n"
                f"- Emphasize quiet, recharging activities.\n"
            )
        elif introvert_score > 0.7:
            introvert_note = (
                f"- {name} is extrovert-leaning (score: {introvert_score:.2f}).\n"
                f"- Include one social or group activity.\n"
            )
        else:
            introvert_note = (
                f"- {name} is balanced socially (score: {introvert_score:.2f}).\n"
                f"- Mix of solo and light social activities is fine.\n"
            )

        return (
            f"You are MindLens — a warm, practical wellbeing coach.\n"
            f"\nUSER CONTEXT:\n"
            f"- Name: {name} | Age group: {age_group}\n"
            f"- Current emotion: {ctx.eos.surface_emotion}\n"
            f"- Mental fatigue: {ctx.eos.mental_fatigue:.2f}\n"
            f"- Distress level: {ctx.eos.distress_level:.2f}\n"
            f"\nPERSONALITY GUIDANCE:\n"
            f"{introvert_note}"
            f"\nINSTRUCTIONS (follow ALL of them):\n"
            f"1. Generate a personalised daily wellness plan for {name}.\n"
            f"2. Structure it as: Morning → Afternoon → Evening.\n"
            f"3. MAX 6 items total across the whole day. Keep it a tiny routine.\n"
            f"4. ALWAYS include a 7-hour sleep block in the evening.\n"
            f"5. Reference their specific situation if known (e.g., exams, work deadline, relationship stress).\n"
            f"6. Make it practical, not generic. Use their name.\n"
            f"7. If age group is 'teen': keep it relatable, mention school/study/friends.\n"
            f"8. If age group is 'adult': mention work, career, relationships, or household.\n"
            f"9. NEVER diagnose. Never suggest medication.\n"
            f"10. End with encouragement: 'You've got this, {name}.'\n"
            f"\nRespond ONLY with the plan. Use simple bullet points. No meta-commentary.\n"
        )

    def _build_user_prompt_v3(self, ctx: AgentContext) -> str:
        return f"User said: {ctx.user_text}"
