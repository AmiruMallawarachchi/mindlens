"""
Journaling Agent — MindLens v3 SYSTEM.md §5.10
=================================================
Trigger: stability_score > 0.3 AND fatigue_score < 0.8 AND user receptive.
Uses Groq 8B (fast, lightweight). Max 120 tokens.

Purpose: Guided thought record (CBT journaling).
Format: 3 structured questions, question 3 uses people_graph to personalize.
"""

from __future__ import annotations

from app.agents.base_agent import AgentContext, AgentOutput, BaseAgent
from app.agents.groq_client import get_groq_client


class JournalingAgent(BaseAgent):
    """
    Provides 3 structured journaling questions that help the user
    process emotions and notice patterns. Uses people_graph to
    personalize question 3.

    Trigger: emotional_stability >= 0.3 AND mental_fatigue < 0.8
             AND receptiveness.journaling >= 0.5
    """

    def __init__(self) -> None:
        super().__init__(
            name="journaling",
            description="Provide 3 reflective journaling questions",
            llm_tier="8B",
            max_tokens=120,
            always_runs=False,
        )

    async def run(self, ctx: AgentContext) -> AgentOutput:
        """Generate exactly 3 journaling questions."""
        # Gating: stability > 0.3 AND fatigue < 0.8 AND receptive to journaling
        if ctx.eos.emotional_stability < 0.3:
            return AgentOutput(
                agent_name=self.name,
                text="",
                metadata={
                    "skipped": True,
                    "reason": f"stability_too_low ({ctx.eos.emotional_stability:.2f} < 0.3)",
                    "llm_tier": "none",
                },
            )
        if ctx.eos.mental_fatigue >= 0.8:
            return AgentOutput(
                agent_name=self.name,
                text="",
                metadata={
                    "skipped": True,
                    "reason": f"fatigue_too_high ({ctx.eos.mental_fatigue:.2f} >= 0.8)",
                    "llm_tier": "none",
                },
            )
        if not ctx.eos.is_receptive_to("journaling"):
            return AgentOutput(
                agent_name=self.name,
                text="",
                metadata={
                    "skipped": True,
                    "reason": f"not_receptive_to_journaling ({ctx.eos.receptiveness.journaling:.2f} < 0.5)",
                    "llm_tier": "none",
                },
            )

        system = self._build_system_prompt_v3(ctx)
        user = self._build_user_prompt_v3(ctx)

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
            text=result.text.strip(),
            metadata={
                "llm_tier": self.llm_tier,
                "tokens_used": result.tokens_used,
                "latency_ms": result.latency_ms,
            },
        )

    def _build_system_prompt_v3(self, ctx: AgentContext) -> str:
        """SYSTEM.md §5.10: 3 structured questions, #3 uses people_graph."""
        name = ctx.user_name or "friend"

        # Question 3 personalization: pick someone from people_graph
        person_name = "a friend"
        person_relationship = "someone close to you"
        if ctx.eos.people_graph:
            person = ctx.eos.people_graph[0]
            person_name = person.name
            person_relationship = person.relationship

        return (
            f"You are MindLens — a warm, emotionally intelligent wellbeing coach.\n"
            f"\nUSER CONTEXT:\n"
            f"- Name: {name}\n"
            f"- Current emotion: {ctx.eos.surface_emotion}\n"
            f"- Session depth: {ctx.eos.session_depth:.2f}\n"
            f"\nINSTRUCTIONS (follow ALL of them):\n"
            f"1. Write EXACTLY 3 reflective journaling questions.\n"
            f"2. Each question should be one sentence.\n"
            f"3. Use {name}'s name in the first line (e.g., 'Here's a quick thought record, {name}:').\n"
            f"4. Question 1: 'What exactly happened? (just the facts)'\n"
            f"5. Question 2: 'What was the first thought that came into your head?'\n"
            f"6. Question 3: 'What would you say to {person_name} if {person_relationship} felt the same way?'\n"
            f"7. Make them feel open, not like homework. No bullet points, no numbered lists.\n"
            f"8. Never diagnose.\n"
            f"\nRespond ONLY with the 3 questions. No intro, no outro.\n"
        )

    def _build_user_prompt_v3(self, ctx: AgentContext) -> str:
        return f"User said: {ctx.user_text}"
