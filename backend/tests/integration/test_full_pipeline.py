"""Integration tests for the MindLens end-to-end pipeline.

Verifies the integration of PII anonymization, Safety Gate checks,
and Orchestrator model processing.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
import pytest

from app.core.anonymizer import anonymize
from app.agents.safety_gate import safety_gate
from app.agents.orchestrator import Orchestrator


@pytest.fixture
def mock_pipeline_results() -> dict:
    """Return mock pipeline results for ModelManager."""
    return {
        "emotion": [
            [{"label": "LABEL_25", "score": 0.85}, {"label": "LABEL_19", "score": 0.3}]  # sadness, nervousness
        ],
        "crisis": [{"label": "NON_CRISIS", "score": 0.1}],
        "mental_health": [
            [{"label": "LABEL_0", "score": 0.75}]  # depression
        ],
    }


class TestMindLensFullPipeline:
    """Validate end-to-end processing flow."""

    @pytest.mark.asyncio
    @patch("app.agents.safety_gate.model_manager")
    @patch("app.models.loader.ModelManager.predict_all")
    async def test_standard_flow_success(
        self,
        mock_predict_all: AsyncMock,
        mock_safety_manager: AsyncMock,
        mock_pipeline_results: dict,
    ) -> None:
        """A normal user turn is anonymized, passes safety, and is routed by the orchestrator."""
        # 1. Mock the models
        mock_safety_manager.predict_crisis = AsyncMock(
            return_value=[{"label": "NON_CRISIS", "score": 0.1}]
        )
        mock_predict_all.return_value = mock_pipeline_results

        # 2. Raw input containing PII (email)
        user_input = "Hey, my email is john@doe.com. I feel very down and sad today."

        # -- Step A: Anonymize --
        clean_input = anonymize(user_input)
        assert "[EMAIL]" in clean_input
        assert "john@doe.com" not in clean_input

        # -- Step B: Safety Gate check --
        safety_status = await safety_gate(clean_input)
        assert safety_status["safe"] is True

        # -- Step C: Orchestration --
        orchestrator = Orchestrator()
        # Ensure our mock matches the orchestrator's ModelManager instance
        orchestrator.models.predict_all = mock_predict_all

        turn_result = await orchestrator.process_turn(clean_input)
        
        # Verify EOS state is returned
        assert "eos" in turn_result
        eos = turn_result["eos"]
        assert eos["surface_emotion"] == "sadness"
        assert eos["core_emotion"] == "sadness"
        assert eos["distress_level"] > 0.4
        
        # Verify routed agents
        assert "empathy" in turn_result["agents"]
        assert turn_result["crisis_flag"] is False

    @pytest.mark.asyncio
    @patch("app.agents.safety_gate.model_manager")
    async def test_crisis_flow_override(
        self,
        mock_safety_manager: AsyncMock,
    ) -> None:
        """A crisis turn is detected by the Safety Gate, bypassing standard orchestrator flow."""
        # Mock safety gate classifier
        mock_safety_manager.predict_crisis = AsyncMock(
            return_value=[{"label": "CRISIS", "score": 0.9}]
        )

        user_input = "I want to end my life right now"

        # -- Step A: Anonymize --
        clean_input = anonymize(user_input)

        # -- Step B: Safety Gate check --
        safety_status = await safety_gate(clean_input)
        assert safety_status["safe"] is False
        assert safety_status["crisis_type"] == "suicidal_ideation"
        assert len(safety_status["resources"]) > 0
        
        # Since it is unsafe, the application logic would bypass orchestrator processing
        # and directly return the crisis templates or route to emergency services.
        assert "Sumithrayo" in [r["name"] for r in safety_status["resources"]]
