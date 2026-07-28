#!/usr/bin/env python3
"""
Spotify MCP Server — MindLens v3 SYSTEM.md §9
================================================
FastAPI server providing SSE transport for Spotify integration.

Modes:
  A: OAuth PKCE (user connected) → full control (search, recommendations, create playlists)
  B: Client credentials (app-level) → search, recommendations only

Endpoints:
  POST /search
  POST /recommendations
  POST /create_playlist (Mode A only)
  GET /status

Usage:
  uvicorn spotify_mcp.server:app --port 8001
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from spotify_mcp.auth import SpotifyAuthManager
from spotify_mcp.spotify_client import SpotifyClient
from spotify_mcp.emotion_mapper import map_emotion_to_features

app = FastAPI(
    title="MindLens Spotify MCP Server",
    description="Music recommendation and playlist management for MindLens",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to MindLens backend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Configuration from env ---
CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
REDIRECT_URI = os.environ.get("SPOTIFY_REDIRECT_URI", "http://localhost:3000/callback")

auth_manager = SpotifyAuthManager(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI)
spotify_client = SpotifyClient(auth_manager)


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=200)
    emotion: str = Field(default="neutral", max_length=50)
    limit: int = Field(default=5, ge=1, le=50)


class RecommendationsRequest(BaseModel):
    audio_features: dict[str, Any] = Field(
        default_factory=dict,
        description="{target_tempo, target_energy, target_valence, ...}"
    )
    genre_seeds: list[str] = Field(default_factory=list)
    limit: int = Field(default=5, ge=1, le=50)


class CreatePlaylistRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    track_uris: list[str] = Field(..., min_length=1)
    user_id: str = Field(..., min_length=1)
    description: str | None = Field(None, max_length=300)


class TrackResponse(BaseModel):
    name: str
    artist: str
    spotify_url: str
    embed_url: str
    preview_url: str | None = None
    uri: str


class StatusResponse(BaseModel):
    mode: str = Field(..., pattern="^(A|B)$")
    connected: bool
    client_id_configured: bool


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/status", response_model=StatusResponse)
async def get_status() -> StatusResponse:
    """
    Return current Spotify connection status.
    Mode A = user OAuth active, Mode B = client credentials only.
    """
    connected = auth_manager.has_user_token()
    mode = "A" if connected else "B"
    return StatusResponse(
        mode=mode,
        connected=connected,
        client_id_configured=bool(CLIENT_ID),
    )


@app.post("/search")
async def search_tracks(req: SearchRequest) -> list[TrackResponse]:
    """
    Search Spotify for tracks matching a query and emotion.
    Uses audio features to refine results.
    """
    if not CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Spotify client credentials not configured",
        )

    try:
        # Map emotion to audio features and build search params
        features = map_emotion_to_features(req.emotion)
        tracks = await spotify_client.search(
            query=req.query,
            audio_features=features,
            limit=req.limit,
        )
        return [
            TrackResponse(
                name=t["name"],
                artist=t["artist"],
                spotify_url=t["spotify_url"],
                embed_url=t["embed_url"],
                preview_url=t.get("preview_url"),
                uri=t["uri"],
            )
            for t in tracks
        ]
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Spotify search failed: {str(exc)}",
        )


@app.post("/recommendations")
async def get_recommendations(req: RecommendationsRequest) -> list[TrackResponse]:
    """
    Get Spotify recommendations based on audio features and genre seeds.
    Works in both Mode A and Mode B.
    """
    if not CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Spotify client credentials not configured",
        )

    try:
        tracks = await spotify_client.recommendations(
            audio_features=req.audio_features,
            genre_seeds=req.genre_seeds,
            limit=req.limit,
        )
        return [
            TrackResponse(
                name=t["name"],
                artist=t["artist"],
                spotify_url=t["spotify_url"],
                embed_url=t["embed_url"],
                preview_url=t.get("preview_url"),
                uri=t["uri"],
            )
            for t in tracks
        ]
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Spotify recommendations failed: {str(exc)}",
        )


@app.post("/create_playlist")
async def create_playlist(req: CreatePlaylistRequest) -> dict[str, Any]:
    """
    Create a Spotify playlist for the user (Mode A only).
    Requires user OAuth token.
    """
    if not auth_manager.has_user_token():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Playlist creation requires user OAuth (Mode A). Connect Spotify first.",
        )

    try:
        playlist = await spotify_client.create_playlist(
            name=req.name,
            track_uris=req.track_uris,
            user_id=req.user_id,
            description=req.description,
        )
        return {
            "playlist_url": playlist["external_urls"]["spotify"],
            "embed_url": f"https://open.spotify.com/embed/playlist/{playlist['id']}",
            "playlist_id": playlist["id"],
            "snapshot_id": playlist["snapshot_id"],
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Playlist creation failed: {str(exc)}",
        )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "spotify-mcp"}
