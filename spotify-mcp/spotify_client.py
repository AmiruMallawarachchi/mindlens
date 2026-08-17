"""
Spotify Client — MindLens v3 SYSTEM.md §9.2
============================================
Async wrapper around the Spotify Web API.
Handles search, recommendations, and playlist creation.
"""

from __future__ import annotations

from typing import Any

import httpx

from auth import SpotifyAuthManager


class SpotifyClient:
    """
    Async Spotify API client with automatic token management.
    """

    BASE_URL = "https://api.spotify.com/v1"

    def __init__(self, auth_manager: SpotifyAuthManager) -> None:
        self.auth = auth_manager

    async def _get_headers(self, user_id: str | None = None) -> dict[str, str]:
        """Get Authorization header with the best available token."""
        token = self.auth.get_active_token(user_id)
        if not token:
            # Try to get app token
            token = await self.auth.get_app_token()
        if not token:
            raise RuntimeError("No Spotify token available")
        return {"Authorization": f"Bearer {token}"}

    # -----------------------------------------------------------------------
    # Search
    # -----------------------------------------------------------------------

    async def search(
        self,
        query: str,
        audio_features: dict[str, Any] | None = None,
        limit: int = 5,
        user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search tracks on Spotify."""
        headers = await self._get_headers(user_id)
        params = {
            "q": query,
            "type": "track",
            "limit": limit,
        }

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/search",
                headers=headers,
                params=params,
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()

        tracks = data.get("tracks", {}).get("items", [])
        return [
            {
                "name": t["name"],
                "artist": ", ".join(a["name"] for a in t["artists"]),
                "spotify_url": t["external_urls"]["spotify"],
                "embed_url": f"https://open.spotify.com/embed/track/{t['id']}",
                "preview_url": t.get("preview_url"),
                "uri": t["uri"],
                "id": t["id"],
            }
            for t in tracks
        ]

    # -----------------------------------------------------------------------
    # Recommendations
    # -----------------------------------------------------------------------

    @staticmethod
    def _mood_terms(energy: float, valence: float) -> str:
        """Turn the numeric targets into words a text search can actually use.

        Coarse on purpose: search matches editorial metadata (titles,
        playlist and album language), not measured signal, so fine-grained
        thresholds would imply a precision this path does not have.
        """
        if energy <= 0.35:
            level = "calm slow"
        elif energy >= 0.7:
            level = "energetic upbeat"
        else:
            level = "mellow"

        if valence <= 0.35:
            colour = "melancholy"
        elif valence >= 0.7:
            colour = "happy"
        else:
            colour = "warm"
        return f"{level} {colour}"

    async def recommendations(
        self,
        audio_features: dict[str, Any],
        genre_seeds: list[str],
        limit: int = 5,
        user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Mood-matched tracks, served from /v1/search.

        This used to call GET /v1/recommendations with seed_genres and
        target_tempo/energy/valence. Spotify deprecated that endpoint (along
        with /audio-features and /recommendations/available-genre-seeds) on
        2024-11-27: applications created after that date receive 403, so for
        any newly registered app the original implementation could not return
        a single track.

        Search is the supported endpoint that remains, so the emotion mapping
        now drives a text query instead of numeric targets. The honest limit
        of that trade: this matches on words, not on measured tempo or
        valence, so it is a looser fit than the old targeting was. Genre and
        broad mood still come through; exact BPM does not.
        """
        mood = self._mood_terms(
            float(audio_features.get("target_energy", 0.5) or 0.5),
            float(audio_features.get("target_valence", 0.5) or 0.5),
        )
        genre = (genre_seeds or ["chill"])[0].replace("-", " ")
        return await self.search(
            query=f"{genre} {mood}",
            limit=limit,
            user_id=user_id,
        )

    # -----------------------------------------------------------------------
    # Playlist creation (Mode A only)
    # -----------------------------------------------------------------------

    async def create_playlist(
        self,
        name: str,
        track_uris: list[str],
        user_id: str,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Create a playlist for the user (requires user token)."""
        headers = await self._get_headers(user_id)

        # Create playlist
        body: dict[str, Any] = {
            "name": name,
            "public": False,
            "description": description or f"MindLens playlist for {user_id}",
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/users/{user_id}/playlists",
                headers=headers,
                json=body,
                timeout=10.0,
            )
            resp.raise_for_status()
            playlist = resp.json()

            # Add tracks
            if track_uris:
                await client.post(
                    f"{self.BASE_URL}/playlists/{playlist['id']}/tracks",
                    headers=headers,
                    json={"uris": track_uris},
                    timeout=10.0,
                )

        return playlist
