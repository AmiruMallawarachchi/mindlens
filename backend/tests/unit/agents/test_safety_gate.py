"""Unit tests for the Safety Gate agent."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
import pytest

from app.agents.safety_gate import (
    layer1_keyword_scan,
    layer2_model_scan,
    safety_gate,
)


class TestSafetyGateKeywordScan:
    """Validate Layer 1 keyword-based scanning."""

    def test_no_matches(self) -> None:
        """Safe text does not trigger keyword scan."""
        result = layer1_keyword_scan("I had a good day at work.")
        assert result["triggered"] is False
        assert len(result["matches"]) == 0

    def test_exact_match(self) -> None:
        """Direct match triggers keywords."""
        result = layer1_keyword_scan("I want to commit suicide")
        assert result["triggered"] is True
        assert "suicide" in result["matches"][0]

    def test_case_insensitive_match(self) -> None:
        """Keywords are case insensitive."""
        result = layer1_keyword_scan("KILL MYSELF right now")
        assert result["triggered"] is True
        assert "kill myself" in result["matches"][0]


class TestSafetyGateModelScan:
    """Validate Layer 2 model-based scanning."""

    @pytest.mark.asyncio
    @patch("app.agents.safety_gate.model_manager")
    async def test_model_no_crisis(self, mock_manager: AsyncMock) -> None:
        """Model returning NON_CRISIS does not trigger."""
        mock_manager.predict_crisis = AsyncMock(
            return_value=[{"label": "NON_CRISIS", "score": 0.1}]
        )
        result = await layer2_model_scan("I am a bit stressed.")
        assert result["triggered"] is False
        assert result["probability"] == 0.1

    @pytest.mark.asyncio
    @patch("app.agents.safety_gate.model_manager")
    async def test_model_crisis(self, mock_manager: AsyncMock) -> None:
        """Model returning CRISIS above threshold triggers."""
        mock_manager.predict_crisis = AsyncMock(
            return_value=[{"label": "CRISIS", "score": 0.85}]
        )
        result = await layer2_model_scan("I can't go on anymore.")
        assert result["triggered"] is True
        assert result["probability"] == 0.85


class TestSafetyGateEndToEnd:
    """Validate safety_gate coordinator function."""

    @pytest.mark.asyncio
    @patch("app.agents.safety_gate.model_manager")
    async def test_safe_passage(self, mock_manager: AsyncMock) -> None:
        """When both layers say safe, safety_gate passes."""
        mock_manager.predict_crisis = AsyncMock(
            return_value=[{"label": "NON_CRISIS", "score": 0.05}]
        )
        result = await safety_gate("I am happy today.")
        assert result["safe"] is True

    @pytest.mark.asyncio
    @patch("app.agents.safety_gate.model_manager")
    async def test_l1_only_triggered(self, mock_manager: AsyncMock) -> None:
        """If only Layer 1 is triggered, safety_gate returns unsafe."""
        mock_manager.predict_crisis = AsyncMock(
            return_value=[{"label": "NON_CRISIS", "score": 0.1}]
        )
        result = await safety_gate("I want to end my life")
        assert result["safe"] is False
        assert 1 in result["layers_triggered"]
        assert result["severity_score"] == 0.9

    @pytest.mark.asyncio
    @patch("app.agents.safety_gate.model_manager")
    async def test_l2_only_triggered(self, mock_manager: AsyncMock) -> None:
        """If only Layer 2 is triggered, safety_gate returns unsafe."""
        mock_manager.predict_crisis = AsyncMock(
            return_value=[{"label": "CRISIS", "score": 0.78}]
        )
        result = await safety_gate("Unobvious crisis text that model catches")
        assert result["safe"] is False
        assert 2 in result["layers_triggered"]
        assert result["severity_score"] == 0.78

    @pytest.mark.asyncio
    @patch("app.agents.safety_gate.model_manager")
    async def test_crisis_type_ideation(self, mock_manager: AsyncMock) -> None:
        """High severity returns suicidal_ideation crisis type."""
        mock_manager.predict_crisis = AsyncMock(
            return_value=[{"label": "CRISIS", "score": 0.95}]
        )
        result = await safety_gate("very high threat text")
        assert result["safe"] is False
        assert result["crisis_type"] == "suicidal_ideation"
        assert len(result["resources"]) > 0
