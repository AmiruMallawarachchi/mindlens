"""
Challenge Agent — MindLens v3 SYSTEM.md §5.6
===============================================
Socratic CBT-style questioning. Gated by trust and stability.
Uses Groq 70B (needs nuance — this is the hardest agent).

Trigger:
- trust_level > 0.6 AND emotional_stability > 0.5 AND receptiveness.challenge > 0.3
- NEVER runs on first session (session_depth < 0.1)
- NEVER runs when distress > 0.7
- Uses distortion_agent output (distortion_label) to base the question on

Output: One Socratic question. Gently curious, not aggressive.
"""

from __future__ import annotations

from app.agents.base_agent import AgentContext, AgentOutput, BaseAgent
from app.agents.groq_client import get_groq_client


class ChallengeAgent(BaseAgent):
    """
    Asks gentle, curious Socratic questions that invite the user to examine
    their automatic thoughts — never confrontational, always respectful.

    Gated by: trust_level > 0.6 AND emotional_stability > 0.5
              AND session_depth >= 0.1
              AND distress_level <= 0.7
              AND receptiveness.challenge >= 0.3
    """

    def __init__(self) -> None:
        super().__init__(
            name="challenge",
            description="Gentle Socratic questioning to examine thoughts",
            llm_tier="70B",  # SYSTEM.md: "needs nuance — this is the hardest agent"
            max_tokens=80,  # One question only
            always_runs=False,
        )

    async def run(self, ctx: AgentContext) -> AgentOutput:
        """Generate a single Socratic question, or skip if gated out."""
        # SYSTEM.md §5.6: Gating logic
        gate_reason = self._should_run(ctx)
        if gate_reason:
            return AgentOutput(
                agent_name=self.name,
                text="",
                metadata={
                    "skipped": True,
                    "reason": gate_reason,
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

    def _should_run(self, ctx: AgentContext) -> str | None:
        """
        Return None if agent should run, otherwise return skip reason.
        SYSTEM.md §5.6: Trust + stability + no crisis + not first session.
        """
        if ctx.eos.session_depth < 0.1:
            return "first_session (session_depth < 0.1)"
        if ctx.eos.distress_level > 0.7:
            return f"distress_too_high ({ctx.eos.distress_level:.2f} > 0.7)"
        if ctx.eos.trust_level < 0.6:
            return f"trust_too_low ({ctx.eos.trust_level:.2f} < 0.6)"
        if ctx.eos.emotional_stability < 0.5:
            return f"stability_too_low ({ctx.eos.emotional_stability:.2f} < 0.5)"
        if ctx.eos.receptiveness.challenge < 0.3:
            return f"challenge_not_receptive ({ctx.eos.receptiveness.challenge:.2f} < 0.3)"
        return None

    def _build_system_prompt_v3(self, ctx: AgentContext) -> str:
        """SYSTEM.md §5.6: One Socratic question based on detected distortion."""
        name = ctx.user_name or "friend"
        age_group = ctx.eos.age_group.value
        distortion_label = ctx.eos.get("distortion_label", "unknown")  # From distortion agent
        distortion_confidence = ctx.eos.get("distortion_confidence", 0.0)

        # Age tone
        tone = "warm and curious" if age_group == "adult" else "casual and curious"

        # Build distortion context if available
        distortion_context = ""
        if distortion_label and distortion_label != "unknown" and distortion_confidence > 0.4:
            distortion_context = (
                f"\nDetected cognitive distortion: {distortion_label} "
                f"(confidence: {distortion_confidence:.0%})\n"
                f"Base your Socratic question on this distortion.\n"
            )

        return (
            f"You are MindLens — a warm, emotionally intelligent wellbeing coach.\n"
            f"\nUSER CONTEXT:\n"
            f"- Name: {name} | Age group: {age_group}\n"
            f"- Current emotion: {ctx.eos.surface_emotion}\n"
            f"- Distress: {ctx.eos.distress_level:.2f}\n"
            f"{distortion_context}"
            f"\nINSTRUCTIONS:\n"
            f"1. Ask ONE Socratic question that gently challenges {name}'s thinking.\n"
            f"2. One question only. Genuinely curious, not aggressive.\n"
            f"3. Frame it as exploration, not correction: 'I'm wondering...' or 'What if...'\n"
            f"4. Base it on the detected cognitive distortion (if available).\n"
            f"5. Age group: {age_group} — tone should be {tone}.\n"
            f"6. Do NOT give the answer. Just ask.\n"
            f"7. NEVER use: 'I understand your feelings', 'That must be hard', 'I hear you'.\n"
            f"8. One sentence. Max 25 words.\n"
            f"\nExamples:\n"
            f"- 'I'm wondering, {name} — what evidence do you have that everyone is judging you?'\n"
            f"- 'What if that one mistake doesn't actually define your whole week, {name}?'\n"
            f"- 'What would you tell Ravi if he felt the same way you do right now?'\n"
            f"\nRespond ONLY with the question. No quotes, no extra text.\n"
        )

    def _build_user_prompt_v3(self, ctx: AgentContext) -> str:
        return f"User said: {ctx.user_text}"
