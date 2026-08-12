"""
Check-In Agent — MindLens v3 SYSTEM.md §5.12
================================================
Trigger: End of every session (writes a pending_checkins entry).
Uses Groq 8B (for the check-in message). Max 80 tokens.

Purpose: Proactive follow-up 22 hours after session end.
Rules:
- Recall something specific from last session
- Ask how they're doing now
- Don't start with "How are you?" — be specific
- 2-3 sentences MAX
"""

from __future__ import annotations

from app.agents.base_agent import AgentContext, AgentOutput, BaseAgent
from app.agents.groq_client import get_groq_client


class CheckInAgent(BaseAgent):
    """
    Generates gentle, personalised check-in messages sent
    proactively between sessions. The chat router schedules
    these into pending_checkins after each session ends.

    Trigger: Background — scheduled at end of session.
    """

    def __init__(self) -> None:
        super().__init__(
            name="checkin",
            description="Generate proactive check-in messages between sessions",
            llm_tier="8B",
            max_tokens=80,
            always_runs=False,
        )

    async def run(self, ctx: AgentContext) -> AgentOutput:
        """Generate a check-in message referencing last session."""
        system = self._build_system_prompt_v3(ctx)
        user = self._build_user_prompt_v3(ctx)

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
            text=result.text.strip(),
            metadata={
                "llm_tier": self.llm_tier,
                "tokens_used": result.tokens_used,
                "latency_ms": result.latency_ms,
            },
        )

    def _build_system_prompt_v3(self, ctx: AgentContext) -> str:
        """SYSTEM.md §5.12: Warm, short, specific check-in."""
        name = ctx.user_name or "friend"
        emotion = ctx.eos.surface_emotion or "unknown"
        distress = ctx.eos.distress_level

        return (
            f"You are MindLens — a warm, thoughtful wellbeing coach.\n"
            f"\nUSER CONTEXT:\n"
            f"- Name: {name}\n"
            f"- Last session emotion: {emotion} (distress: {distress:.2f})\n"
            f"\nINSTRUCTIONS (follow ALL of them):\n"
            f"1. Write a warm, SHORT (2-3 sentences) proactive check-in message for {name}.\n"
            f"2. Recall something specific from the last session (e.g., a person they mentioned, an event, a worry).\n"
            f"3. Ask how they're doing now.\n"
            f"4. Do NOT start with 'How are you?' — be specific instead.\n"
            f"5. Example: 'Hey {name} — I've been thinking about you. How did that conversation with Ravi go? And how's the sleep been?'\n"
            f"6. Another example: 'Hey {name}, you were feeling pretty anxious about your exam last time. How are things today?'\n"
            f"7. Sound like a friend checking in, not a bot.\n"
            f"8. NEVER diagnose.\n"
            f"\nRespond ONLY with the check-in message. No quotes, no meta-commentary.\n"
        )

    def _build_user_prompt_v3(self, ctx: AgentContext) -> str:
        # Build context from last session if available
        last_topic = "their recent concern"
        if ctx.session_history and len(ctx.session_history) > 1:
            # Try to extract a key topic from the last user message
            last_user_msg = None
            for turn in reversed(ctx.session_history):
                if turn.get("role") == "user":
                    last_user_msg = turn.get("text", "")
                    break
            if last_user_msg:
                last_topic = last_user_msg[:100]  # Truncate for context

        return (
            f"Generate a check-in message for {ctx.user_name or 'friend'}.\n"
            f"Last session summary: feeling {ctx.eos.surface_emotion} about {last_topic}.\n"
            f"Distress level at end of last session: {ctx.eos.distress_level:.2f}."
        )
