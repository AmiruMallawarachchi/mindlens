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

Secrets are read from env only â€” never hardcoded.
"""

from __future__ import annotations

import asyncio
from contextvars import ContextVar
from typing import Any

from app.agents.groq_stub import build_stub_response
from app.agents.groq_types import GroqResponse

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
    "8B": "openai/gpt-oss-20b",
    "70B": "openai/gpt-oss-120b",
}

# Both current models are reasoning models: unlike llama-3.1/3.3, they spend
# completion tokens on hidden chain-of-thought before the visible answer.
# Confirmed live: at "low" effort that overhead is ~7-10 tokens; at default
# effort it can run 80+ tokens and, combined with an agent's own max_tokens
# budget, silently produces empty content (all of it spent on reasoning,
# none left for the answer). This app wants a fast, direct, in-character
# reply, not deliberation, so every call pins effort low.
_REASONING_EFFORT = "low"

# Per-agent max tokens (from SYSTEM.md Â§25.2)
DEFAULT_MAX_TOKENS = 200


# ---------------------------------------------------------------------------
# Degradation tracking
# ---------------------------------------------------------------------------
# When Groq is unreachable, rate-limited or misconfigured, chat() falls back to
# a canned template. That is the correct fallback, but silently serving
# hardcoded text as if it were generated therapy is not acceptable â€” a wrong
# API key during a live demo would look exactly like a working system.
#
# The sink is a mutable set held in a ContextVar. asyncio tasks copy the
# context at creation but share the referenced object, so degradations recorded
# inside agents dispatched via asyncio.gather remain visible to the caller.

_degradation_sink: ContextVar[set[str] | None] = ContextVar(
    "groq_degradation_sink", default=None
)


def begin_degradation_tracking() -> set[str]:
    """Start a fresh degradation sink for one pipeline run. Returns the sink."""
    sink: set[str] = set()
    _degradation_sink.set(sink)
    return sink


def _record_degradation(reason: str) -> None:
    """Note that this turn's output is not fully model-generated."""
    sink = _degradation_sink.get()
    if sink is not None:
        sink.add(reason)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


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
                "Install with: pip install groq"
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
                    reasoning_effort=_REASONING_EFFORT,
                ),
                timeout=timeout,
            )
        except TimeoutError:
            logger.error("Groq call timed out after %.1fs", timeout)
            _record_degradation("timeout")
            return GroqResponse(
                text="I'm having a moment â€” please try again in a few seconds.",
                model_used=model_id,
                tokens_used=0,
                latency_ms=timeout * 1000,
                finish_reason="timeout",
            )
        except Exception as exc:
            logger.exception("Groq API error: %s", exc)
            _record_degradation("api_error")
            return self._stub_response(
                system_prompt, user_prompt, model_tier, max_tokens
            )

        elapsed = (asyncio.get_event_loop().time() - start) * 1000
        content = response.choices[0].message.content or ""
        usage = response.usage

        if not content.strip():
            # A 200 with empty content is not a success â€” it just doesn't
            # look like a failure to the caller, which is exactly how this
            # went unnoticed. It reached response_assembler as a real
            # AgentOutput with text="", and when that agent was the only
            # one speaking, the whole turn silently degraded to the generic
            # "I'm here with you. Tell me more." with nothing recorded to
            # say why.
            #
            # The known cause: on a reasoning model, the completion budget
            # can be spent entirely on hidden chain-of-thought
            # (usage.completion_tokens_details.reasoning_tokens) before any
            # visible text is written, leaving content empty even though the
            # call itself succeeded. reasoning_effort="low" above cuts this
            # sharply but doesn't guarantee zero â€” a tight max_tokens on a
            # long prompt can still exhaust it.
            reasoning_tokens = getattr(
                getattr(usage, "completion_tokens_details", None), "reasoning_tokens", None
            )
            logger.warning(
                "Groq call returned empty content (model=%s, finish_reason=%s, "
                "reasoning_tokens=%s) â€” falling back to a stub reply",
                model_id,
                response.choices[0].finish_reason,
                reasoning_tokens,
            )
            _record_degradation("empty_completion")
            return self._stub_response(
                system_prompt, user_prompt, model_tier, max_tokens
            )

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
        Not yet fully implemented â€” falls back to non-streaming.
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
        return build_stub_response(
            system_prompt, user_prompt, model_tier, max_tokens, _record_degradation
        )


# Module-level singleton
_groq_client: GroqClient | None = None


def get_groq_client() -> GroqClient:
    """Return the singleton Groq client."""
    global _groq_client
    if _groq_client is None:
        _groq_client = GroqClient()
    return _groq_client
