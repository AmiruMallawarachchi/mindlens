"""Shared fixtures for focused orchestrator unit tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.agents.orchestrator import Orchestrator

@pytest.fixture(autouse=True)
def _stub_groq():
    """Pin the Groq singleton to a stub for every test in this module.

    Every class here that calls run_full_pipeline or process_turn was
    otherwise making a real Groq API call per test — one took 104s and then
    failed on a 429 rate limit. Routing, EOS construction and telemetry are
    what this file tests; none of it needs the network, and a flaky external
    dependency in a unit suite is a bug in the suite.
    """
    from unittest.mock import AsyncMock, MagicMock

    from app.agents import groq_client as groq_module

    stub = MagicMock()
    stub.chat = AsyncMock(
        return_value=MagicMock(
            text="A steady reply.",
            model_used="stub",
            tokens_used=8,
            latency_ms=1.0,
            finish_reason="stop",
        )
    )
    previous = groq_module._groq_client
    groq_module._groq_client = stub
    yield stub
    groq_module._groq_client = previous


@pytest.fixture
def mock_model_manager() -> MagicMock:
    """Return a mocked ModelManager with predictable outputs."""
    mock = MagicMock()
    mock.predict_all = AsyncMock(return_value={
        "emotion": [
            [{"label": "LABEL_25", "score": 0.85}, {"label": "LABEL_19", "score": 0.6}]
        ],
        "crisis": [{"label": "NON_CRISIS", "score": 0.12}],
        "mental_health": [
            [{"label": "LABEL_1", "score": 0.7}, {"label": "LABEL_0", "score": 0.3}]
        ],
    })
    return mock


@pytest.fixture
def orchestrator(mock_model_manager: MagicMock) -> Orchestrator:
    """Return Orchestrator with injected mock."""
    orch = Orchestrator()
    orch.models = mock_model_manager
    orch._retriever = MagicMock()
    orch._retriever.retrieve.return_value = []
    return orch


