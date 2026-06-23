"""
Spotify Auth Manager — MindLens v3 SYSTEM.md §9.1
====================================================
Handles both authentication modes:
  Mode A: OAuth PKCE (user connected, full access)
  Mode B: Client credentials (app-level, search/recommend only)

Token storage: Encrypted in MongoDB (user_spotify collection).
Fernet encryption with env key.
"""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
import time
from typing import Any

try:
    from cryptography.fernet import Fernet
    _FERNET_AVAILABLE = True
except ImportError:
    _FERNET_AVAILABLE = False


class SpotifyAuthManager:
    """
    Manages Spotify authentication for both modes.
    
    Mode A (User OAuth):
      - PKCE flow: code_challenge + code_verifier
      - Access token + refresh token stored encrypted
      - Can: search, recommendations, create playlists, user library
    
    Mode B (App credentials):
      - Client credentials flow
      - App-level access token (no user data)
      - Can: search, recommendations only
    """

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

        # Mode B: app-level token (cached)
        self._app_token: str | None = None
        self._app_token_expiry: float = 0.0

        # Mode A: user tokens (per-user, stored externally via MongoDB)
        self._user_tokens: dict[str, dict[str, Any]] = {}
        # Fernet encryption key from env
        self._fernet: Any = None
        if _FERNET_AVAILABLE:
            key = os.environ.get("FERNET_KEY", "")
            if key:
                self._fernet = Fernet(key.encode())

    # -----------------------------------------------------------------------
    # Mode B: Client Credentials
    # -----------------------------------------------------------------------

    async def get_app_token(self) -> str | None:
        """Get or refresh the app-level client credentials token."""
        if self._app_token and time.time() < self._app_token_expiry - 60:
            return self._app_token

        if not self.client_id or not self.client_secret:
            return None

        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://accounts.spotify.com/api/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            self._app_token = data["access_token"]
            self._app_token_expiry = time.time() + data.get("expires_in", 3600)
            return self._app_token

    # -----------------------------------------------------------------------
    # Mode A: OAuth PKCE
    # -----------------------------------------------------------------------

    def generate_pkce(self) -> tuple[str, str, str]:
        """Generate PKCE code_verifier, code_challenge, and state."""
        verifier = base64.urlsafe_b64encode(
            secrets.token_bytes(32)
        ).decode().rstrip("=")
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()
        ).decode().rstrip("=")
        state = secrets.token_urlsafe(16)
        return verifier, challenge, state

    def get_authorize_url(self, state: str, code_challenge: str) -> str:
        """Build the Spotify OAuth authorize URL."""
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": "playlist-modify-private playlist-modify-public user-read-private",
            "state": state,
            "code_challenge_method": "S256",
            "code_challenge": code_challenge,
        }
        from urllib.parse import urlencode
        return f"https://accounts.spotify.com/authorize?{urlencode(params)}"

    async def exchange_code(
        self, code: str, code_verifier: str
    ) -> dict[str, Any] | None:
        """Exchange authorization code for access + refresh tokens."""
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://accounts.spotify.com/api/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                    "client_id": self.client_id,
                    "code_verifier": code_verifier,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if resp.status_code != 200:
                return None
            return resp.json()

    async def refresh_user_token(self, refresh_token: str) -> dict[str, Any] | None:
        """Refresh a user's access token."""
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://accounts.spotify.com/api/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": self.client_id,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if resp.status_code != 200:
                return None
            return resp.json()

    # -----------------------------------------------------------------------
    # Token storage (in-memory cache; persist via MongoDB in production)
    # -----------------------------------------------------------------------

    def store_user_token(self, user_id: str, token_data: dict[str, Any]) -> None:
        """Store user token (encrypted if Fernet is available)."""
        if self._fernet:
            token_data = {
                k: self._fernet.encrypt(v.encode()).decode() if isinstance(v, str) else v
                for k, v in token_data.items()
            }
        self._user_tokens[user_id] = token_data

    def get_user_token(self, user_id: str) -> dict[str, Any] | None:
        """Retrieve user token (decrypt if Fernet is available)."""
        data = self._user_tokens.get(user_id)
        if data and self._fernet:
            data = {
                k: self._fernet.decrypt(v.encode()).decode() if isinstance(v, str) else v
                for k, v in data.items()
            }
        return data

    def has_user_token(self, user_id: str | None = None) -> bool:
        """Check if any user token is available."""
        if user_id:
            return user_id in self._user_tokens
        return bool(self._user_tokens)

    def get_active_token(self, user_id: str | None = None) -> str | None:
        """Get the best available token (Mode A first, then Mode B)."""
        if user_id and user_id in self._user_tokens:
            return self._user_tokens[user_id].get("access_token")
        return self._app_token
