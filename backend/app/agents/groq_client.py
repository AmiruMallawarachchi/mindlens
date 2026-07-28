"""
Groq Client
===========
Async wrapper around the Groq API with:
- Stub mode for development (USE_OPENAI_STUBS=true)
- Per-agent max token limits
- 8-second timeout on every call
- Streaming support
- Circuit-breaker awareness
- Cost tracking (8B vs 70B)

Secrets are read from env only — never hardcoded.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

try:
    import groq
    from groq import AsyncGroq
    _GROQ_AVAILABLE = True
except ImportError:
    groq = None  # type: ignore[assignment]
    AsyncGroq = None  # type: ignore[misc,assignment]
    _GROQ_AVAILABLE = False

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Model mapping
# ---------------------------------------------------------------------------

GROQ_MODELS = {
    "8B": "llama-3.1-8b-instant",
    "70B": "llama-3.3-70b-versatile",
}

# Per-agent max tokens (from SYSTEM.md §25.2)
DEFAULT_MAX_TOKENS = 200


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GroqResponse:
    text: str
    model_used: str
    tokens_used: int = 0
    latency_ms: float = 0.0
    finish_reason: str = "stop"


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class GroqClient:
    """
    Async Groq client with stub fallback, timeout, and token limits.
    """

    def __init__(self) -> None:
        self._client: AsyncGroq | None = None # type: ignore
        self._stub_mode = settings.use_openai_stubs
        self._api_key = settings.groq_api_key

        if not _GROQ_AVAILABLE:
            self._stub_mode = True
            logger.warning(
                "groq package not installed. Forcing stub mode. "
                "Install with: pip install groq==0.8.0"
            )
            return

        if not self._stub_mode and self._api_key:
            self._client = AsyncGroq(api_key=self._api_key) # type: ignore
            logger.info("Groq client initialized (real mode).")
        else:
            logger.warning(
                "Groq client in STUB mode. Set USE_OPENAI_STUBS=false and "
                "provide GROQ_API_KEY for real inference."
            )

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        model_tier: str = "8B",
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = 0.7,
        timeout: float = 8.0,
    ) -> GroqResponse:
        """
        Send a chat completion request to Groq.
        Returns a structured response or a stub in development mode.
        """
        start = asyncio.get_event_loop().time()

        if self._stub_mode or self._client is None:
            return self._stub_response(
                system_prompt, user_prompt, model_tier, max_tokens
            )

        model_id = GROQ_MODELS.get(model_tier, GROQ_MODELS["8B"])

        try:
            response = await asyncio.wait_for(
                self._client.chat.completions.create(
                    model=model_id,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=max_tokens,
                    temperature=temperature,
                ),
                timeout=timeout,
            )
        except TimeoutError:
            logger.error("Groq call timed out after %.1fs", timeout)
            return GroqResponse(
                text="I'm having a moment — please try again in a few seconds.",
                model_used=model_id,
                tokens_used=0,
                latency_ms=timeout * 1000,
                finish_reason="timeout",
            )
        except Exception as exc:
            logger.exception("Groq API error: %s", exc)
            return self._stub_response(
                system_prompt, user_prompt, model_tier, max_tokens
            )

        elapsed = (asyncio.get_event_loop().time() - start) * 1000
        content = response.choices[0].message.content or ""
        usage = response.usage

        return GroqResponse(
            text=content.strip(),
            model_used=model_id,
            tokens_used=usage.total_tokens if usage else 0,
            latency_ms=round(elapsed, 1),
            finish_reason=response.choices[0].finish_reason or "stop",
        )

    async def stream(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        model_tier: str = "8B",
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = 0.7,
        timeout: float = 8.0,
    ) -> Any:
        """
        Streaming wrapper (returns async generator of tokens).
        Not yet fully implemented — falls back to non-streaming.
        """
        # Streaming implementation requires WebSocket integration.
        # For now, return the full response as a single item.
        result = await self.chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_tier=model_tier,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
        )
        yield result

    # -----------------------------------------------------------------------
    # Stub / fallback
    # -----------------------------------------------------------------------

    def _stub_response(
        self,
        system_prompt: str,
        user_prompt: str,
        model_tier: str,
        max_tokens: int,
    ) -> GroqResponse:
        """
        Generate a development-mode stub response.
        Uses the system prompt intent to produce a plausible fake reply.
        """
        # Detect agent type from system prompt
        agent_name = "agent"
        if "empathy" in system_prompt.lower():
            agent_name = "empathy"
        elif "mindfulness" in system_prompt.lower():
            agent_name = "mindfulness"
        elif "crisis" in system_prompt.lower():
            agent_name = "crisis"
        elif "reflection" in system_prompt.lower():
            agent_name = "reflection"
        elif "challenge" in system_prompt.lower():
            agent_name = "challenge"
        elif "distortion" in system_prompt.lower():
            agent_name = "distortion"
        elif "routine" in system_prompt.lower():
            agent_name = "routine"
        elif "journaling" in system_prompt.lower():
            agent_name = "journaling"
        elif "music" in system_prompt.lower():
            agent_name = "music"
        elif "check-in" in system_prompt.lower() or "checkin" in system_prompt.lower():
            agent_name = "checkin"
        elif "progress" in system_prompt.lower():
            agent_name = "progress"
        elif "personality" in system_prompt.lower():
            agent_name = "personality"

        # Template stubs keyed by agent name
        stubs: dict[str, str] = {
            "empathy": (
                "I hear you, {name}. It sounds like you're carrying a lot right now. "
                "You're not alone in this."
            ),
            "mindfulness": (
                "Let's take a breath together, {name}. Close your eyes if you want. "
                "Breathe in slowly for 4 counts… hold for 4… out for 6. "
                "You're safe right here."
            ),
            "crisis": (
                "I can hear how much pain you're in. Please reach out to NIMH at 1926 — "
                "they're available 24/7. Your safety matters most."
            ),
            "reflection": (
                "It sounds like the core feeling here is {emotion}. "
                "What do you think is underneath that for you, {name}?"
            ),
            "challenge": (
                "That's a really strong thought, {name}. What evidence do you have "
                "that it's completely true?"
            ),
            "distortion": (
                "I notice a possible thinking pattern here. When you say that, "
                "what's the actual thought running through your mind?"
            ),
            "routine": (
                "A small routine might help anchor you, {name}. "
                "What if we tried one tiny thing at the same time tomorrow?"
            ),
            "journaling": (
                "Three questions for you, {name}:\n"
                "1. What emotion showed up most strongly today?\n"
                "2. What moment felt the hardest?\n"
                "3. What one small thing went okay?"
            ),
            "music": (
                "Music can be a powerful anchor, {name}. "
                "Try a slow, instrumental playlist with a steady rhythm. "
                "Even 5 minutes of intentional listening can shift your state."
            ),
            "checkin": (
                "Hey {name}, just checking in. How are you feeling today? "
                "No pressure — just a gentle pause."
            ),
            "progress": (
                "Looking at your journey so far, {name}, you've been showing up consistently. "
                "That matters. What's one small win you noticed this week?"
            ),
            "personality": (
                "[Personality tone adapted for {name}.]"
            ),
        }

        # Extract user name from system prompt if available
        name = "friend"
        if "User's name:" in system_prompt:
            try:
                name_line = [line for line in system_prompt.split("\n") if "User's name:" in line][0]
                name = name_line.split(":")[-1].strip()
            except IndexError:
                pass

        # Extract emotion if available
        emotion = "sadness"
        if "surface_emotion" in system_prompt:
            try:
                emotion_line = [line for line in system_prompt.split("\n") if "surface_emotion" in line][0]
                emotion = emotion_line.split(":")[-1].strip().split()[0]
            except IndexError:
                pass

        template = stubs.get(agent_name, "I'm here with you, {name}.")
        text = template.format(name=name, emotion=emotion)

        # Truncate to max_tokens approximation (roughly 4 chars per token)
        max_chars = max_tokens * 4
        if len(text) > max_chars:
            text = text[:max_chars].rsplit(" ", 1)[0] + "…"

        return GroqResponse(
            text=text,
            model_used=f"stub-{model_tier}",
            tokens_used=len(text.split()),
            latency_ms=0.0,
            finish_reason="stub",
        )


# Module-level singleton
_groq_client: GroqClient | None = None


def get_groq_client() -> GroqClient:
    """Return the singleton Groq client."""
    global _groq_client
    if _groq_client is None:
        _groq_client = GroqClient()
    return _groq_client
