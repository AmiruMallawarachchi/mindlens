"""
Emotion Mapper — MindLens v3 SYSTEM.md §9.3
============================================
Maps emotional states to Spotify audio features and genre seeds.

Used by: Music agent, Spotify MCP server.
"""

from __future__ import annotations

from typing import Any


# SYSTEM.md §5.11: Emotion → Audio Feature Mapping
EMOTION_MAP: dict[str, dict[str, Any]] = {
    "anxiety": {
        "target_tempo": 67,
        "target_energy": 0.30,
        "target_valence": 0.40,
        "genres": ["ambient", "classical", "piano", "sleep"],
    },
    "fear": {
        "target_tempo": 67,
        "target_energy": 0.30,
        "target_valence": 0.40,
        "genres": ["ambient", "classical", "piano"],
    },
    "panic": {
        "target_tempo": 60,
        "target_energy": 0.20,
        "target_valence": 0.35,
        "genres": ["ambient", "rain-sounds", "new-age"],
    },
    "sadness": {
        "target_tempo": 60,
        "target_energy": 0.20,
        "target_valence": 0.20,
        "genres": ["indie", "acoustic", "folk", "piano"],
    },
    "grief": {
        "target_tempo": 55,
        "target_energy": 0.15,
        "target_valence": 0.15,
        "genres": ["indie", "acoustic", "piano", "classical"],
    },
    "anger": {
        "target_tempo": 90,
        "target_energy": 0.60,
        "target_valence": 0.50,
        "genres": ["rock", "alternative", "punk", "metal"],
    },
    "joy": {
        "target_tempo": 120,
        "target_energy": 0.80,
        "target_valence": 0.90,
        "genres": ["pop", "dance", "disco", "happy"],
    },
    "excitement": {
        "target_tempo": 120,
        "target_energy": 0.80,
        "target_valence": 0.90,
        "genres": ["pop", "dance", "electronic", "party"],
    },
    "neutral": {
        "target_tempo": 80,
        "target_energy": 0.40,
        "target_valence": 0.60,
        "genres": ["lo-fi", "chill", "indie-pop", "acoustic"],
    },
    "numbness": {
        "target_tempo": 80,
        "target_energy": 0.40,
        "target_valence": 0.60,
        "genres": ["lo-fi", "chill", "ambient"],
    },
    "burnout": {
        "target_tempo": 62,
        "target_energy": 0.30,
        "target_valence": 0.50,
        "genres": ["nature", "ambient", "new-age", "sleep"],
    },
    "stress": {
        "target_tempo": 70,
        "target_energy": 0.30,
        "target_valence": 0.40,
        "genres": ["ambient", "classical", "piano"],
    },
}


def map_emotion_to_features(emotion: str) -> dict[str, Any]:
    """
    Map a MindLens emotion label to Spotify audio features.
    Returns a dict with target_tempo, target_energy, target_valence, genres.
    """
    emotion_lower = emotion.lower().strip()
    return EMOTION_MAP.get(
        emotion_lower,
        {
            "target_tempo": 80,
            "target_energy": 0.40,
            "target_valence": 0.60,
            "genres": ["lo-fi", "chill", "indie-pop"],
        },
    )


def get_genre_seeds(emotion: str) -> list[str]:
    """Get Spotify genre seeds for a given emotion."""
    return map_emotion_to_features(emotion).get("genres", ["lo-fi", "chill"])
