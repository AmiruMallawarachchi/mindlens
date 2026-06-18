"""Unit tests for Orchestrator EOS builder and routing."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.agents.orchestrator import Orchestrator


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
    return orch


class TestOrchestratorProcessTurn:
    """End-to-end turn processing with mocked models."""

    @pytest.mark.asyncio
    async def test_returns_eos_and_agents(self, orchestrator: Orchestrator) -> None:
        """process_turn returns EOS snapshot + agent list."""
        result = await orchestrator.process_turn("I feel anxious about work")
        assert "eos" in result
        assert "agents" in result
        assert "crisis_flag" in result

    @pytest.mark.asyncio
    async def test_crisis_flag_false_when_safe(self, orchestrator: Orchestrator) -> None:
        """Mocked crisis score 0.12 < 0.45 threshold."""
        result = await orchestrator.process_turn("safe text")
        assert result["crisis_flag"] is False

    @pytest.mark.asyncio
    async def test_empathy_always_present(self, orchestrator: Orchestrator) -> None:
        """Empathy agent runs on every turn."""
        result = await orchestrator.process_turn("any text")
        assert "empathy" in result["agents"]

    @pytest.mark.asyncio
    async def test_mindfulness_for_anxiety(self, orchestrator: Orchestrator) -> None:
        """Anxious core emotion triggers mindfulness."""
        result = await orchestrator.process_turn("anxious text")
        assert "mindfulness" in result["agents"]

    @pytest.mark.asyncio
    async def test_crisis_override_routes_only_crisis(self, orchestrator: Orchestrator) -> None:
        """If crisis_flag=True, only crisis agent runs."""
        orchestrator.models.predict_all = AsyncMock(return_value={
            "emotion": [[{"label": "LABEL_25", "score": 0.9}]],
            "crisis": [{"label": "CRISIS", "score": 0.85}],
            "mental_health": [[{"label": "LABEL_1", "score": 0.5}]],
        })
        result = await orchestrator.process_turn("suicidal text")
        assert result["crisis_flag"] is True
        assert result["agents"] == ["crisis"]


class TestOrchestratorParsing:
    """Static helper methods."""

    def test_parse_multilabel_flat(self) -> None:
        """Flatten list[list[dict]] into dict."""
        raw = [[{"label": "LABEL_0", "score": 0.9}, {"label": "LABEL_1", "score": 0.4}]]
        label_map = {"LABEL_0": "a", "LABEL_1": "b"}
        parsed = Orchestrator._parse_multilabel(raw, label_map)
        assert parsed == {"a": 0.9, "b": 0.4}

    def test_parse_multilabel_mixed(self) -> None:
        """Handles mixed list[dict] and list[list[dict]] shapes."""
        raw = [{"label": "LABEL_0", "score": 0.8}]
        label_map = {"LABEL_0": "a"}
        parsed = Orchestrator._parse_multilabel(raw, label_map)
        assert parsed == {"a": 0.8}

    def test_argmax(self) -> None:
        assert Orchestrator._argmax({"a": 0.1, "b": 0.9, "c": 0.5}) == "b"

    def test_argmax_empty(self) -> None:
        assert Orchestrator._argmax({}) == "neutral"

    def test_pick_core_emotion_negative(self) -> None:
        """Selects highest negative emotion."""
        scores = {"joy": 0.9, "sadness": 0.7, "anger": 0.6}
        assert Orchestrator._pick_core_emotion(scores) == "sadness"

    def test_pick_core_emotion_fallback(self) -> None:
        """Falls back to overall highest when no negatives."""
        scores = {"joy": 0.9, "admiration": 0.5}
        assert Orchestrator._pick_core_emotion(scores) == "joy"

    def test_pick_suppressed(self) -> None:
        """Returns second-highest different from surface."""
        scores = {"a": 0.9, "b": 0.7, "c": 0.3}
        assert Orchestrator._pick_suppressed(scores, "a") == "b"

    def test_compute_distress(self) -> None:
        """Weighted composite in range 0–1."""
        emotion = {"sadness": 0.8}
        mh = {"anxiety": 0.6}
        crisis = 0.2
        distress = Orchestrator._compute_distress(emotion, mh, crisis)
        assert 0.0 <= distress <= 1.0
        assert round(distress, 3) == 0.508
