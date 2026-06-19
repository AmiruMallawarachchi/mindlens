"""
Music Agent
===========
Recommends music and grounding techniques.
Runs when distress >= 0.4 or user is receptive to music.
Uses Groq 8B (max 200 tokens).
"""

from __future__ import annotations

from app.agents.base_agent import AgentContext, AgentOutput, BaseAgent
from app.agents.groq_client import get_groq_client


class MusicAgent(BaseAgent):
    """
    Suggests music-based interventions: curated playlists,
    grounding through listening, or rhythmic breathing.
    """

    def __init__(self) -> None:
        super().__init__(
            name="music",
            description="Recommend music and grounding through sound",
            llm_tier="8B",
            max_tokens=200,
            always_runs=False,
        )

    async def run(self, ctx: AgentContext) -> AgentOutput:
        """Generate a music recommendation."""
        system = self._build_system_prompt(ctx)
        user = self._build_user_prompt(ctx)

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
            text=result.text,
            metadata={
                "llm_tier": self.llm_tier,
                "tokens_used": result.tokens_used,
                "latency_ms": result.latency_ms,
            },
        )

    def _build_system_prompt(self, ctx: AgentContext) -> str:
        emotion = ctx.eos.core_emotion or ctx.eos.surface_emotion

        # Map emotion to music type
        music_type = "calming instrumental"
        if emotion in {"anger", "annoyance", "frustration"}:
            music_type = "slow, grounding instrumental or ambient"
        elif emotion in {"sadness", "grief", "remorse"}:
            music_type = "gentle, melancholic instrumental or soft acoustic"
        elif emotion in {"anxiety", "fear", "nervousness"}:
            music_type = "steady-rhythm ambient or binaural beats"
        elif emotion in {"joy", "excitement", "optimism"}:
            music_type = "uplifting acoustic or light instrumental"

        return (
            f"You are the Music Agent of MindLens.\n"
            f"Your role: {self.description}\n"
            f"User's name: {ctx.user_name}\n"
            f"Core emotion: {emotion}\n"
            f"Receptiveness to music: {ctx.eos.receptiveness.music:.2f}\n"
            "\nMUSIC TYPE TO SUGGEST:\n"
            f"{music_type}\n"
            "\nINSTRUCTIONS:\n"
            "1. Suggest one music-based grounding technique.\n"
            "2. Mention a genre or specific type (e.g., 'ambient', 'lo-fi', 'classical piano').\n"
            "3. Explain WHY that type fits their current state.\n"
            "4. Keep it to 3-4 sentences.\n"
            "5. Use their name.\n"
            "6. Never diagnose.\n"
        )

    def _build_user_prompt(self, ctx: AgentContext) -> str:
        return f"User said: {ctx.user_text}"
