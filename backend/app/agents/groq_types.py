"""Shared result type returned by the hosted Groq client."""

from dataclasses import dataclass


@dataclass(frozen=True)
class GroqResponse:
    text: str
    model_used: str
    tokens_used: int = 0
    latency_ms: float = 0.0
    finish_reason: str = "stop"
