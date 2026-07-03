"""
Music Agent — MindLens v3 SYSTEM.md §5.11
============================================
Trigger: distress > 0.4 OR user requests music.
Uses Groq 8B (for message wrapping only).

Spotify MCP Integration:
  Mode A (User connected): Full OAuth → search/recommendations/create playlists
  Mode B (Not connected): Client credentials → search/recommendations
  Fallback chain: Spotify → YouTube links → static curated list

EMOTION → AUDIO FEATURES (SYSTEM.md §5.11):
  anxiety/fear     → tempo: 60-75, energy: 0.2-0.4, valence: 0.3-0.5, genre: ambient/classical
  sadness/grief    → tempo: 50-70, energy: 0.1-0.3, valence: 0.1-0.3, genre: indie/acoustic
  anger            → tempo: 80-100, energy: 0.5-0.7, valence: 0.4-0.6, genre: rock/alternative
  joy/excitement   → tempo: 110-130, energy: 0.7-0.9, valence: 0.8-1.0, genre: pop/dance
  numbness/flat    → tempo: 70-90, energy: 0.3-0.5, valence: 0.5-0.7, genre: lo-fi/chill
  burnout          → tempo: 55-70, energy: 0.2-0.4, valence: 0.4-0.6, genre: nature/ambient
"""

from __future__ import annotations

import os

from app.agents.base_agent import AgentContext, AgentOutput, BaseAgent
from app.agents.groq_client import get_groq_client
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Emotion → audio feature mapping (SYSTEM.md §5.11)
EMOTION_AUDIO_FEATURES = {
    "anxiety":     {"tempo": (60, 75),   "energy": (0.2, 0.4), "valence": (0.3, 0.5), "genres": ["ambient", "classical"]},
    "fear":        {"tempo": (60, 75),   "energy": (0.2, 0.4), "valence": (0.3, 0.5), "genres": ["ambient", "classical"]},
    "panic":       {"tempo": (60, 75),   "energy": (0.2, 0.4), "valence": (0.3, 0.5), "genres": ["ambient", "classical"]},
    "sadness":     {"tempo": (50, 70),   "energy": (0.1, 0.3), "valence": (0.1, 0.3), "genres": ["indie", "acoustic"]},
    "grief":       {"tempo": (50, 70),   "energy": (0.1, 0.3), "valence": (0.1, 0.3), "genres": ["indie", "acoustic"]},
    "anger":       {"tempo": (80, 100),  "energy": (0.5, 0.7), "valence": (0.4, 0.6), "genres": ["rock", "alternative"]},
    "joy":         {"tempo": (110, 130), "energy": (0.7, 0.9), "valence": (0.8, 1.0), "genres": ["pop", "dance"]},
    "excitement":  {"tempo": (110, 130), "energy": (0.7, 0.9), "valence": (0.8, 1.0), "genres": ["pop", "dance"]},
    "neutral":     {"tempo": (70, 90),   "energy": (0.3, 0.5), "valence": (0.5, 0.7), "genres": ["lo-fi", "chill"]},
    "numbness":    {"tempo": (70, 90),   "energy": (0.3, 0.5), "valence": (0.5, 0.7), "genres": ["lo-fi", "chill"]},
    "burnout":     {"tempo": (55, 70),   "energy": (0.2, 0.4), "valence": (0.4, 0.6), "genres": ["nature", "ambient"]},
    "stress":      {"tempo": (60, 80),   "energy": (0.2, 0.4), "valence": (0.3, 0.5), "genres": ["ambient", "classical"]},
}

# Static fallback tracks (royalty-free / well-known, used when Spotify is down)
STATIC_FALLBACK = {
    "anxiety": [
        {"name": "Weightless", "artist": "Marconi Union", "spotify_url": "https://open.spotify.com/track/6k3KWxKmnJ8e", "youtube_url": "https://www.youtube.com/watch?v=UfcAVejslrU"},
        {"name": "Clair de Lune", "artist": "Claude Debussy", "spotify_url": "https://open.spotify.com/track/6CuJQ3WlX", "youtube_url": "https://www.youtube.com/watch?v=WNcsurk"},
    ],
    "sadness": [
        {"name": "Holocene", "artist": "Bon Iver", "spotify_url": "https://open.spotify.com/track/1", "youtube_url": "https://www.youtube.com/watch?v=2"},
    ],
}


class MusicAgent(BaseAgent):
    """
    Recommends music based on emotion, using Spotify MCP server.

    Mode A: User connected (OAuth) → personalized playlists
    Mode B: App-level (Client credentials) → track recommendations
    Fallback: YouTube links → static curated list
    """

    def __init__(self) -> None:
        super().__init__(
            name="music",
            description="Recommend music and grounding through sound",
            llm_tier="8B",
            max_tokens=200,
            always_runs=False,
        )
        # MCP client endpoint (Spotify MCP server)
        self._mcp_base_url = os.environ.get("SPOTIFY_MCP_URL", "http://localhost:8001")

    async def run(self, ctx: AgentContext) -> AgentOutput:
        """
        Generate music recommendation via Spotify MCP or fallback chain.
        """
        emotion = (ctx.eos.core_emotion or ctx.eos.surface_emotion or "neutral").lower()
        audio_features = EMOTION_AUDIO_FEATURES.get(
            emotion,
            {"tempo": (70, 90), "energy": (0.3, 0.5), "valence": (0.5, 0.7), "genres": ["lo-fi", "chill"]}
        )

        # Try Spotify MCP first
        try:
            spotify_result = await self._call_spotify_mcp(ctx, emotion, audio_features)
            if spotify_result:
                return spotify_result
        except Exception as exc:
            logger.warning("Spotify MCP failed: %s. Falling back to LLM + static.", exc)

        # Fallback: LLM-generated message with static track list
        return await self._llm_fallback(ctx, emotion, audio_features)

    async def _call_spotify_mcp(
        self, ctx: AgentContext, emotion: str, audio_features: dict
    ) -> AgentOutput | None:
        """
        Call Spotify MCP server.
        Returns AgentOutput with music metadata, or None on failure.
        """
        import httpx

        async with httpx.AsyncClient(timeout=5.0) as client:
            # Check Spotify connection status
            try:
                status_resp = await client.get(f"{self._mcp_base_url}/status")
                status = status_resp.json()
            except Exception:
                return None

            mode = status.get("mode", "B")
            connected = status.get("connected", False)

            # Get recommendations based on audio features
            rec_payload = {
                "audio_features": {
                    "target_tempo": (audio_features["tempo"][0] + audio_features["tempo"][1]) // 2,
                    "target_energy": (audio_features["energy"][0] + audio_features["energy"][1]) / 2,
                    "target_valence": (audio_features["valence"][0] + audio_features["valence"][1]) / 2,
                },
                "genre_seeds": audio_features["genres"],
                "limit": 5,
            }

            rec_resp = await client.post(
                f"{self._mcp_base_url}/recommendations",
                json=rec_payload,
            )
            tracks = rec_resp.json().get("tracks", [])

            if not tracks:
                return None

            # Mode A: Create playlist if connected
            playlist_data = None
            if mode == "A" and connected:
                try:
                    playlist_payload = {
                        "name": f"MindLens — {emotion.title()} ({ctx.user_name or 'friend'})",
                        "track_uris": [t.get("uri", "") for t in tracks if t.get("uri")],
                        "user_id": "current_user",  # Will be resolved by MCP server
                    }
                    pl_resp = await client.post(
                        f"{self._mcp_base_url}/create_playlist",
                        json=playlist_payload,
                    )
                    playlist_data = pl_resp.json()
                except Exception as exc:
                    logger.warning("Playlist creation failed: %s", exc)

            # Build LLM-wrapped message
            tracks_info = "\n".join(
                f"- {t['name']} by {t['artist']}"
                for t in tracks[:3]
            )

            # Groq LLM wrapping
            groq_client = get_groq_client()
            wrap_result = await groq_client.chat(
                system_prompt=self._build_music_wrapper_prompt(ctx, emotion, audio_features),
                user_prompt=f"Here are the tracks:\n{tracks_info}",
                model_tier=self.llm_tier,
                max_tokens=self.max_tokens,
                temperature=0.7,
            )

            return AgentOutput(
                agent_name=self.name,
                text=wrap_result.text.strip(),
                metadata={
                    "llm_tier": self.llm_tier,
                    "tokens_used": wrap_result.tokens_used,
                    "latency_ms": wrap_result.latency_ms,
                    "spotify_mode": mode,
                    "tracks": tracks,
                    "playlist": playlist_data,
                    "emotion": emotion,
                },
            )

    async def _llm_fallback(
        self, ctx: AgentContext, emotion: str, audio_features: dict
    ) -> AgentOutput:
        """LLM fallback when Spotify is unavailable."""
        groq_client = get_groq_client()

        # Get static fallback tracks for this emotion
        fallback_tracks = STATIC_FALLBACK.get(emotion, STATIC_FALLBACK.get("anxiety", []))
        tracks_str = "\n".join(
            f"- {t['name']} by {t['artist']} (Spotify: {t.get('spotify_url', 'N/A')}, YouTube: {t.get('youtube_url', 'N/A')})"
            for t in fallback_tracks
        )

        system = self._build_music_wrapper_prompt(ctx, emotion, audio_features)
        user = (
            f"Spotify is not available. Use these fallback tracks and suggest the user connect Spotify for personalized playlists.\n"
            f"Tracks:\n{tracks_str}\n"
            f"Suggest genres: {', '.join(audio_features['genres'])}."
        )

        result = await groq_client.chat(
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
                "spotify_mode": "unavailable",
                "tracks": fallback_tracks,
                "connect_prompt": True,
                "emotion": emotion,
            },
        )

    def _build_music_wrapper_prompt(self, ctx: AgentContext, emotion: str, audio_features: dict) -> str:
        """Build the LLM system prompt for wrapping music recommendations."""
        name = ctx.user_name or "friend"
        genres = ", ".join(audio_features["genres"])
        tempo = (audio_features["tempo"][0] + audio_features["tempo"][1]) // 2
        energy = (audio_features["energy"][0] + audio_features["energy"][1]) / 2

        return (
            f"You are MindLens — a warm, thoughtful wellbeing coach.\n"
            f"\nUSER CONTEXT:\n"
            f"- Name: {name}\n"
            f"- Current emotion: {emotion}\n"
            f"- Recommended music style: {genres} (tempo ~{tempo} BPM, energy {energy:.1f})\n"
            f"\nINSTRUCTIONS (follow ALL of them):\n"
            f"1. Write a warm, brief message introducing the music recommendation.\n"
            f"2. Explain WHY this music style fits their current emotion ({emotion}).\n"
            f"3. Mention 1-3 specific tracks or genres.\n"
            f"4. If Spotify is connected, suggest creating a playlist.\n"
            f"5. If Spotify is NOT connected, suggest connecting it for full experience, and provide YouTube links as fallback.\n"
            f"6. Keep it to 3-4 sentences.\n"
            f"7. Use their name once.\n"
            f"8. NEVER diagnose.\n"
            f"9. Never use: 'I understand your feelings', 'That must be hard', 'I hear you'.\n"
            f"\nRespond ONLY with the music recommendation message. No meta-commentary.\n"
        )

    def _build_user_prompt(self, ctx: AgentContext) -> str:
        return f"User is feeling {ctx.eos.surface_emotion}. Recommend music."
