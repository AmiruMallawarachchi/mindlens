"""
Mindfulness Agent — MindLens v3 SYSTEM.md §5.8
=================================================
Runs when distress > 0.5 OR core_emotion in [anxiety, fear, panic].
Uses Groq 8B (fast, lightweight). Max 250 tokens.

Purpose: Generate a SHORT, personalized guided exercise (not a static script).
Rules:
- Maximum 5 steps
- Use their name once
- Speak directly to them: "Close your eyes, {nickname}..."
- Choose: 4-7-8 breathing / box breathing / 5-4-3-2-1 grounding / body scan
  (pick the best for surface_emotion)
- Sound like a calm friend, not a YouTube wellness video
- Do NOT say "I'd like to guide you through..." or "Let's begin our session"
"""

from __future__ import annotations

from app.agents.base_agent import AgentContext, AgentOutput, BaseAgent
from app.agents.groq_client import get_groq_client

# Emotion → best technique mapping (SYSTEM.md §5.8 + §5.11)
EMOTION_TECHNIQUE = {
    "anxiety": "4-7-8 breathing or 5-4-3-2-1 grounding (gentle, anchoring)",
    "fear": "box breathing (steady, predictable rhythm)",
    "panic": "5-4-3-2-1 grounding (immediate sensory anchoring)",
    "anger": "box breathing (cooling down, steady rhythm)",
    "sadness": "body scan (gentle awareness, self-compassion)",
    "grief": "body scan (gentle awareness, self-compassion)",
    "stress": "4-7-8 breathing (slowing down the nervous system)",
    "overwhelm": "5-4-3-2-1 grounding (reduce sensory overload)",
    "neutral": "4-7-8 breathing (gentle relaxation)",
}


class MindfulnessAgent(BaseAgent):
    """
    Delivers personalized, short grounding exercises based on distress
    level and current emotion. NOT a static script — LLM-generated
    with user name and context.

    Trigger: distress > 0.5 OR core_emotion in [anxiety, fear, panic].
    """

    def __init__(self) -> None:
        super().__init__(
            name="mindfulness",
            description="Provide personalized grounding and breathing exercises",
            llm_tier="8B",
            max_tokens=250,
            always_runs=False,
        )

    async def run(self, ctx: AgentContext) -> AgentOutput:
        """Generate a personalized, warm mindfulness exercise."""
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
        """SYSTEM.md §5.8: Short, warm, personalized mindfulness exercise."""
        name = ctx.user_name or "friend"
        distress = ctx.eos.distress_level
        emotion = ctx.eos.surface_emotion or "neutral"

        # Pick technique based on emotion
        technique = EMOTION_TECHNIQUE.get(
            emotion.lower(),
            "4-7-8 breathing or 5-4-3-2-1 grounding"
        )

        # Time guidance based on distress
        time_note = "about 2 minutes"
        if distress >= 0.8:
            time_note = "quick — 1 minute, emergency grounding"
        elif distress >= 0.6:
            time_note = "about 2 minutes"
        else:
            time_note = "about 3 minutes, gentle relaxation"

        return (
            f"You are MindLens — a calm, warm wellbeing coach.\n"
            f"\nUSER CONTEXT:\n"
            f"- Name: {name}\n"
            f"- Age group: {ctx.eos.age_group.value}\n"
            f"- Current emotion: {emotion} (distress: {distress:.2f})\n"
            f"- Preferred technique: {technique}\n"
            f"\nINSTRUCTIONS (follow ALL of them):\n"
            f"1. Generate a SHORT, warm mindfulness exercise for {name} RIGHT NOW.\n"
            f"2. Maximum 5 steps. Number them (1., 2., 3., 4., 5.).\n"
            f"3. Use their name ONCE, naturally.\n"
            f"4. Speak directly to them: 'Close your eyes, {name}...' or 'Breathe in slowly, {name}...'\n"
            f"5. Choose the technique based on their emotion: {technique}.\n"
            f"6. Sound like a calm friend, NOT a YouTube wellness video.\n"
            f"7. Do NOT say: 'I'd like to guide you through...' or 'Let's begin our session' or 'Welcome to this meditation.'\n"
            f"8. Keep it warm, simple, and actionable. No jargon.\n"
            f"9. This should take {time_note}.\n"
            f"10. End with a gentle encouragement, not a sales pitch.\n"
            f"\nRespond ONLY with the exercise. No intro, no outro, no meta-commentary.\n"
        )

    def _build_user_prompt_v3(self, ctx: AgentContext) -> str:
        return f"User is feeling {ctx.eos.surface_emotion} (distress: {ctx.eos.distress_level:.2f}). Please give them a grounding exercise."

    def _build_user_prompt(self, ctx: AgentContext) -> str:
        return f"User said: {ctx.user_text}"
