"""
Music Agent — MindLens v3 SYSTEM.md §5.11
============================================
Trigger: distress > 0.4 OR user requests music.
Uses Groq 8B (for message wrapping only).

Track source: Apple's iTunes Search API (https://itunes.apple.com/search).
No auth, no client registration, no user connection step — a plain
unauthenticated GET. This replaced a Spotify Web API integration
(spotify-mcp/, now removed) that could not actually be finished: Spotify's
Web API has required the *developer's own account* to hold an active
Premium subscription since February/March 2026, on top of the
/recommendations endpoint (which the original design targeted) having been
withdrawn for new apps back in November 2024. iTunes search needs none of
that, and returns a 30-second preview MP3 the client can play directly —
something the Spotify path never reached either, since it only ever linked
out to open Spotify.

EMOTION → SEARCH MOOD (replaces the old tempo/energy/valence targets):
  anxiety/fear/panic → ambient, calm, slow, instrumental
  sadness/grief      → acoustic, gentle, soft
  anger              → alternative, steady, grounding
  joy/excitement     → upbeat, bright, pop
  numbness/flat      → lo-fi, chill
  burnout            → ambient, nature, slow
"""

from __future__ import annotations

import random
from typing import Any

import httpx

from app.agents.base_agent import AgentContext, AgentOutput, BaseAgent
from app.agents.groq_client import get_groq_client
from app.utils.logger import get_logger

logger = get_logger(__name__)

ITUNES_SEARCH_URL = "https://itunes.apple.com/search"

# Emotion -> (genre, mood words). Used to build the iTunes search term
# directly — no numeric audio-feature targets, because a text search has
# nothing to target them against. Coarse and word-based on purpose.
# Every label the emotion classifier can actually emit gets a mapping.
#
# This previously listed 12 moods, only 7 of which the classifier ever
# produces — it emits the 28 GoEmotions classes (core/emotion_labels.py),
# so 21 of them missed the map entirely and fell through to the default.
# The default was "chill lo-fi", iTunes returns a deterministic result set
# for a fixed query, and the agent always played the first hit. That is the
# whole reason every reply offered "Coffee Break - Lo-Fi Chill Cafe" no
# matter what the user said: "confusion", "disappointment", "nervousness"
# and eighteen others all resolved to the same search, and that search's
# first result never changes.
#
# Mood terms are kept to one or two words on purpose. Three-word moods
# looked more precise but matched almost nothing in iTunes' catalogue --
# "acoustic reflective mellow" returned literally zero results, so that
# emotion silently fell through to the static fallback on every single
# turn. Every query below was checked against the live API for a usable
# result count rather than assumed to work.
#
# Several emotions deliberately share a target — the useful axis here is
# what the music needs to *do* (settle, lift, hold steady), not a distinct
# genre per label.
EMOTION_SEARCH_TERMS: dict[str, dict[str, Any]] = {
    # Distress and agitation -> settle the nervous system
    "anxiety":        {"genre": "ambient",     "mood": "calm peaceful"},
    "nervousness":    {"genre": "ambient",     "mood": "calm peaceful"},
    "fear":           {"genre": "ambient",     "mood": "calm peaceful"},
    "panic":          {"genre": "ambient",     "mood": "calm peaceful"},
    "stress":         {"genre": "ambient",     "mood": "relaxing calm"},
    "burnout":        {"genre": "ambient",     "mood": "nature sounds rest"},
    "embarrassment":  {"genre": "ambient",     "mood": "soft warm"},
    "confusion":      {"genre": "instrumental", "mood": "focus clarity calm"},

    # Low mood -> sit with it rather than force brightness
    "sadness":        {"genre": "acoustic",    "mood": "melancholy"},
    "grief":          {"genre": "piano",       "mood": "reflective"},
    "disappointment": {"genre": "acoustic",    "mood": "reflective"},
    "remorse":        {"genre": "piano",       "mood": "reflective quiet"},

    # Heat -> steady rather than stoke
    "anger":          {"genre": "instrumental", "mood": "grounding"},
    "annoyance":      {"genre": "instrumental", "mood": "steady focus"},
    "disgust":        {"genre": "instrumental", "mood": "steady grounding"},
    "disapproval":    {"genre": "instrumental", "mood": "steady calm"},

    # Bright -> match the lift
    "joy":            {"genre": "pop",         "mood": "upbeat happy"},
    "excitement":     {"genre": "pop",         "mood": "energetic upbeat"},
    "amusement":      {"genre": "pop",         "mood": "playful light"},
    "optimism":       {"genre": "indie",       "mood": "hopeful bright"},
    "pride":          {"genre": "indie",       "mood": "uplifting"},
    "gratitude":      {"genre": "acoustic",    "mood": "warm uplifting"},
    "relief":         {"genre": "ambient",     "mood": "uplifting"},
    "admiration":     {"genre": "indie",       "mood": "warm bright"},
    "approval":       {"genre": "indie",       "mood": "warm easy"},

    # Tender / reflective
    "love":           {"genre": "soul",        "mood": "warm romantic"},
    "caring":         {"genre": "acoustic",    "mood": "warm tender"},
    "desire":         {"genre": "soul",        "mood": "smooth warm"},
    "curiosity":      {"genre": "instrumental", "mood": "curious light"},
    "realization":    {"genre": "instrumental", "mood": "reflective open"},
    "surprise":       {"genre": "indie",       "mood": "bright"},

    # Flat
    "neutral":        {"genre": "lofi",        "mood": "chill study"},
    "numbness":       {"genre": "ambient",     "mood": "spacious"},
}
_DEFAULT_SEARCH_TERM = {"genre": "chill", "mood": "lo-fi"}

# Used only if iTunes itself is unreachable (network/rate-limit) — a track
# name and artist to name in the fallback message, no fabricated links.
STATIC_FALLBACK = {
    "anxiety": [
        {"name": "Weightless", "artist": "Marconi Union"},
        {"name": "Clair de Lune", "artist": "Claude Debussy"},
    ],
    "sadness": [
        {"name": "Holocene", "artist": "Bon Iver"},
    ],
}


class MusicAgent(BaseAgent):
    """Recommends music based on emotion, via the iTunes Search API."""

    def __init__(self) -> None:
        super().__init__(
            name="music",
            description="Recommend music and grounding through sound",
            llm_tier="8B",
            max_tokens=200,
            always_runs=False,
        )

    async def run(self, ctx: AgentContext) -> AgentOutput:
        emotion = (ctx.eos.core_emotion or ctx.eos.surface_emotion or "neutral").lower()
        search_terms = EMOTION_SEARCH_TERMS.get(emotion, _DEFAULT_SEARCH_TERM)

        try:
            tracks = await self._search_itunes(search_terms, limit=5)
            if tracks:
                return await self._build_output(ctx, emotion, search_terms, tracks)
        except Exception as exc:
            logger.warning("iTunes search failed: %s. Falling back to static list.", exc)

        return await self._static_fallback(ctx, emotion, search_terms)

    async def _search_itunes(
        self, search_terms: dict[str, Any], limit: int
    ) -> list[dict[str, Any]]:
        """Query iTunes; map its response into this agent's track shape.

        `previewUrl` is a real, directly-playable 30-second clip — present
        on most but not all tracks. `trackViewUrl` (the Apple Music page)
        is present whenever previewUrl is, so a track never has neither.

        Overfetches and dedupes by (name, artist): the same song genuinely
        appears more than once in iTunes' catalog under different trackIds
        when it's been released on multiple compilation albums — common for
        the generic mood-library music these searches tend to surface. The
        card only shows name and artist, so an undeduped result rendered as
        the same track listed two or three times in a row.
        """
        query = f"{search_terms['genre']} {search_terms['mood']}"
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                ITUNES_SEARCH_URL,
                params={
                    "term": query,
                    "media": "music",
                    "entity": "song",
                    # Deliberately the API maximum rather than limit*4.
                    # iTunes returns a stable, identically-ordered result set
                    # for a fixed query, so taking the top few and playing the
                    # first meant the same song forever for a given emotion. A
                    # wide pool is what makes the shuffle below meaningful.
                    "limit": 200,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        seen: set[tuple[str, str]] = set()
        tracks: list[dict[str, Any]] = []
        for t in data.get("results", []):
            name = t.get("trackName")
            if not name:
                continue
            artist = t.get("artistName", "Unknown artist")
            key = (name.strip().lower(), artist.strip().lower())
            if key in seen:
                continue
            seen.add(key)
            tracks.append({
                "name": name,
                "artist": artist,
                "preview_url": t.get("previewUrl"),
                "track_url": t.get("trackViewUrl"),
            })

        # Prefer tracks that can actually be played in-app. A track with no
        # previewUrl can only offer an outbound Apple Music link, so putting
        # one first would hand the user a dead-end card when a playable
        # alternative existed in the same result set.
        playable = [t for t in tracks if t["preview_url"]]
        pool = playable or tracks

        # iTunes' ordering is deterministic; without this the same emotion
        # returns the same track every single turn, which is exactly what it
        # did. Shuffling a wide pool is what makes the suggestion feel chosen
        # rather than hardcoded — and it keeps every track on the card from
        # the same emotion-matched search, so variety never costs relevance.
        random.shuffle(pool)
        return pool[:limit]

    async def _build_output(
        self,
        ctx: AgentContext,
        emotion: str,
        search_terms: dict[str, Any],
        tracks: list[dict[str, Any]],
    ) -> AgentOutput:
        groq_client = get_groq_client()
        tracks_info = "\n".join(f"- {t['name']} by {t['artist']}" for t in tracks[:3])

        wrap_result = await groq_client.chat(
            system_prompt=self._build_music_wrapper_prompt(ctx, emotion, search_terms),
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
                "tracks": tracks,
                "emotion": emotion,
            },
        )

    async def _static_fallback(
        self, ctx: AgentContext, emotion: str, search_terms: dict[str, Any]
    ) -> AgentOutput:
        """LLM fallback when iTunes itself is unreachable."""
        groq_client = get_groq_client()

        fallback_tracks = STATIC_FALLBACK.get(emotion, STATIC_FALLBACK.get("anxiety", []))
        # Name and artist only — these carry no URLs, and the prompt below
        # is explicit that none should be invented.
        tracks_str = "\n".join(f"- {t['name']} by {t['artist']}" for t in fallback_tracks)

        system = self._build_music_wrapper_prompt(ctx, emotion, search_terms)
        user = (
            f"Track search is temporarily unavailable. Mention these instead, "
            f"without claiming they're currently playable:\n{tracks_str}\n"
            f"Style to reach for: {search_terms['genre']}, {search_terms['mood']}."
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
                "tracks": fallback_tracks,
                "emotion": emotion,
            },
        )

    def _build_music_wrapper_prompt(
        self, ctx: AgentContext, emotion: str, search_terms: dict[str, Any]
    ) -> str:
        """Build the LLM system prompt for wrapping music recommendations."""
        name = ctx.user_name or "friend"

        return (
            f"You are MindLens — a warm, thoughtful wellbeing coach.\n"
            f"\nUSER CONTEXT:\n"
            f"- Name: {name}\n"
            f"- Current emotion: {emotion}\n"
            f"- Recommended style: {search_terms['genre']}, {search_terms['mood']}\n"
            f"\nINSTRUCTIONS (follow ALL of them):\n"
            f"1. Write a warm, brief message introducing the music recommendation.\n"
            f"2. Explain WHY this style fits their current emotion ({emotion}).\n"
            f"3. Mention 1-3 specific tracks or the style by name.\n"
            f"4. The track plays right here in the app — never mention Spotify,\n"
            f"   connecting an account, or any other platform.\n"
            f"5. Never write a URL or link of any kind: you are not given any,\n"
            f"   and an invented one is worse than none. The interface handles\n"
            f"   playback on its own.\n"
            f"6. Keep it to 3-4 sentences.\n"
            f"7. Use their name once.\n"
            f"8. NEVER diagnose.\n"
            f"9. Never use: 'I understand your feelings', 'That must be hard', 'I hear you'.\n"
            f"\nRespond ONLY with the music recommendation message. No meta-commentary.\n"
        )

    def _build_user_prompt(self, ctx: AgentContext) -> str:
        return f"User is feeling {ctx.eos.surface_emotion}. Recommend music."
