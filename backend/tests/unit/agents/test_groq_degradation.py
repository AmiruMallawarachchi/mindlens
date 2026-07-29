"""
Tests for LLM degradation tracking.

When Groq is unreachable, misconfigured or rate-limited, GroqClient serves a
canned template. That fallback is correct, but it must never be indistinguishable
from real model output — a wrong API key during a live demo would otherwise look
exactly like a working system.
"""

from __future__ import annotations

import asyncio

import pytest
from app.agents.groq_client import (
    GroqClient,
    _degradation_sink,
    begin_degradation_tracking,
)


@pytest.fixture
def stub_client() -> GroqClient:
    """A client forced into stub mode, as it is when no API key is set."""
    client = GroqClient()
    client._stub_mode = True
    client._client = None
    return client


@pytest.mark.asyncio
async def test_stub_response_is_recorded(stub_client: GroqClient) -> None:
    sink = begin_degradation_tracking()
    result = await stub_client.chat("You are the empathy agent", "hello")

    assert result.finish_reason == "stub"
    assert "stub" in sink


@pytest.mark.asyncio
async def test_degradation_is_visible_across_asyncio_gather(
    stub_client: GroqClient,
) -> None:
    """
    The orchestrator dispatches agents via asyncio.gather. Tasks copy the
    context at creation, so a plain ContextVar assignment inside a task would
    NOT propagate back. The sink is a shared mutable set for exactly this
    reason — this test pins that behaviour.
    """
    sink = begin_degradation_tracking()

    async def run_agent(index: int):
        return await stub_client.chat(f"agent {index}", "hello")

    await asyncio.gather(*[run_agent(i) for i in range(4)])

    assert "stub" in sink, "degradation recorded inside gather() was lost"


@pytest.mark.asyncio
async def test_each_pipeline_run_starts_clean(stub_client: GroqClient) -> None:
    first = begin_degradation_tracking()
    await stub_client.chat("You are the empathy agent", "hello")
    assert first == {"stub"}

    second = begin_degradation_tracking()
    assert second == set(), "sink leaked between pipeline runs"


@pytest.mark.asyncio
async def test_recording_outside_a_tracked_run_is_a_noop(
    stub_client: GroqClient,
) -> None:
    """Calls made outside run_full_pipeline must not raise."""
    _degradation_sink.set(None)
    result = await stub_client.chat("You are the empathy agent", "hello")
    assert result.finish_reason == "stub"


@pytest.mark.asyncio
async def test_healthy_call_records_nothing() -> None:
    """A real completion must leave the sink empty."""

    class _Message:
        content = "You are carrying a lot right now."

    class _Choice:
        message = _Message()
        finish_reason = "stop"

    class _Usage:
        total_tokens = 42

    class _Completion:
        choices = [_Choice()]
        usage = _Usage()

    class _Completions:
        async def create(self, **_kwargs):
            return _Completion()

    class _Chat:
        completions = _Completions()

    class _FakeGroq:
        chat = _Chat()

    client = GroqClient()
    client._stub_mode = False
    client._client = _FakeGroq()

    sink = begin_degradation_tracking()
    result = await client.chat("You are the empathy agent", "hello")

    assert result.finish_reason == "stop"
    assert result.text == "You are carrying a lot right now."
    assert sink == set(), f"healthy call flagged as degraded: {sink}"
