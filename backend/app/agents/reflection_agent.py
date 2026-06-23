"""
Reflection Agent — MindLens v3 SYSTEM.md §5.5
================================================
Runs when session_depth > 0.3 (after turn 3+ in a session).
Uses Groq 8B (fast, lightweight). Max 50 tokens.

Purpose: Ensure emotional validation happened BEFORE any advice or challenge.
Output: Short validation sentence that gets prepended to the response.

RULES:
- Only runs when session_depth > 0.3
- In ONE sentence, validate the user's emotion.
- Do NOT give advice. Do NOT ask questions. Just reflect back.
- Make it feel genuine, not clinical. Use their name once.
- Never: "I understand your feelings." "That must be hard." "I hear you."
"""

from __future__ import annotations

from app.agents.base_agent import AgentContext, AgentOutput, BaseAgent
from app.agents.groq_client import get_groq_client


class ReflectionAgent(BaseAgent):
    """
    Reflects back the user's experience in a concise, validating way.
    Helps them feel heard and often surfaces the core emotion.
    Trigger: session_depth > 0.3.
    """

    def __init__(self) -> None:
        super().__init__(
            name="reflection",
            description="Summarise and reframe the user's emotional experience",
            llm_tier="8B",
            max_tokens=50,  # SYSTEM.md: max 50 tokens = 1 sentence
            always_runs=False,
        )

    async def run(self, ctx: AgentContext) -> AgentOutput:
        """Generate a one-sentence reflection (SYSTEM.md §5.5)."""
        # STRICT gate: only runs when session_depth > 0.3
        if ctx.eos.session_depth <= 0.3:
            return AgentOutput(
                agent_name=self.name,
                text="",
                metadata={
                    "skipped": True,
                    "reason": "session_depth <= 0.3",
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
                "skipped": False,
            },
        )

    def _build_system_prompt_v3(self, ctx: AgentContext) -> str:
        """SYSTEM.md §5.5: ONE sentence, validate emotion, use name, no advice."""
        name = ctx.user_name or "friend"
        emotion = ctx.eos.surface_emotion or "unknown"

        return (
            f"You are MindLens — a warm, emotionally intelligent wellbeing coach.\n"
            f"\nUSER CONTEXT:\n"
            f"- Name: {name}\n"
            f"- Current emotion: {emotion}\n"
            f"\nINSTRUCTIONS:\n"
            f"1. Write ONE sentence that validates {name}'s emotion ({emotion}).\n"
            f"2. Do NOT give advice. Do NOT ask questions. Just reflect their feeling back.\n"
            f"3. Make it feel genuine, not clinical. Use their name once.\n"
            f"4. Example: 'It sounds like you're feeling really anxious about this, {name}.'\n"
            f"5. Example: 'That sounds like it really hurts, {name}.'\n"
            f"6. NEVER use: 'I understand your feelings', 'That must be hard', 'I hear you'.\n"
            f"7. ONE sentence only. No more.\n"
            f"\nRespond ONLY with the reflection sentence. No quotes, no meta-commentary.\n"
        )

    def _build_user_prompt_v3(self, ctx: AgentContext) -> str:
        return f"User said: {ctx.user_text}"
