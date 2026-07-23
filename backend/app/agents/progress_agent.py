"""
Progress Agent — MindLens v3 SYSTEM.md §5.13
===============================================
Trigger: Every 7 sessions OR user clicks "Progress" in right panel.
Uses Groq 70B (needs pattern synthesis across sessions). Max 350 tokens.

Purpose: Generate weekly insight summary.
Output: Shown in right panel Dashboard view.
Includes:
- Mood trend over last 7 days
- Most common emotion
- Most effective coping strategy
- One observation about growth
- Suggestion for next week
Tone: Encouraging. Data-backed. Specific to them.
"""

from __future__ import annotations

from app.agents.base_agent import AgentContext, AgentOutput, BaseAgent
from app.agents.groq_client import get_groq_client


class ProgressAgent(BaseAgent):
    """
    Summarises trends, celebrates small wins, and gently
    notes patterns across the user's session history.

    Trigger: Requires ≥ 7 sessions to generate meaningful insight.
             (The orchestrator controls this gating.)
    """

    def __init__(self) -> None:
        super().__init__(
            name="progress",
            description="Provide weekly insights into progress and growth",
            llm_tier="70B",  # SYSTEM.md: "needs pattern synthesis"
            max_tokens=350,
            always_runs=False,
        )

    def _build_system_prompt(self, ctx: AgentContext) -> str:
        return self._build_system_prompt_v3(ctx)

    def _build_user_prompt(self, ctx: AgentContext) -> str:
        return self._build_user_prompt_v3(ctx)

    async def run(self, ctx: AgentContext) -> AgentOutput:
        """Generate a progress insight based on session history."""

        system = self._build_system_prompt_v3(ctx)
        user = self._build_user_prompt_v3(ctx)

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
            text=result.text.strip(),
            metadata={
                "llm_tier": self.llm_tier,
                "tokens_used": result.tokens_used,
                "latency_ms": result.latency_ms,
            },
        )

    def _build_system_prompt_v3(self, ctx: AgentContext) -> str:
        """SYSTEM.md §5.13: Encouraging, data-backed, specific."""
        name = ctx.user_name or "friend"
        age_group = ctx.eos.age_group.value

        return (
            f"You are MindLens — a warm, encouraging wellbeing coach.\n"
            f"\nUSER CONTEXT:\n"
            f"- Name: {name} | Age group: {age_group}\n"
            f"- Alliance score: {ctx.eos.alliance_score:.2f}\n"
            f"\nINSTRUCTIONS (follow ALL of them):\n"
            f"1. Generate a weekly insight summary for {name}.\n"
            f"2. Structure it as 4-5 short paragraphs:\n"
            f"   - Mood trend: how emotions shifted over the last 7 sessions.\n"
            f"3. MAX 6 items total across the whole day. Keep it tiny routine.\n"
            f"   - Most effective coping strategy: what seemed to help them most.\n"
            f"   - One observation about growth: what you notice they're getting better at.\n"
            f"   - Suggestion for next week: one gentle, practical idea.\n"
            f"3. Tone: encouraging, data-backed, specific to them. Not generic.\n"
            f"4. Use their name 1-2 times naturally.\n"
            f"5. If age group is 'teen': keep it casual, relatable.\n"
            f"6. If age group is 'adult': slightly deeper, more structured.\n"
            f"7. NEVER diagnose. Never compare to others.\n"
            f"8. Never use: 'I understand ...'\n"
            f"9. Celebrate specific small wins without exaggerating them.\n"
            f"\nRespond ONLY with the insight summary. No bullet points. Use simple paragraphs.\n"
        )

    def _build_user_prompt_v3(self, ctx: AgentContext) -> str:
        # Build session history summary for the prompt
        history_summary = ""
        if ctx.session_history:
            emotions = [turn.get("emotion", "unknown") for turn in ctx.session_history[-7:]]
            history_summary = f"Recent emotions (last 7 sessions): {', '.join(emotions)}."
        else:
            history_summary = "No recent session data available."

        return (
            f"Generate a weekly progress insight for {ctx.user_name or 'friend'}.\n"
            f"{history_summary}\n"
            f"Current emotional state: {ctx.eos.surface_emotion} (distress: {ctx.eos.distress_level:.2f}).\n"
            f"Alliance score: {ctx.eos.alliance_score:.2f}."
        )
