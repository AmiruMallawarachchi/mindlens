"""Integration coverage for privacy, safety, and orchestration boundaries."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from app.agents.orchestrator import Orchestrator
from app.core.anonymizer import anonymize


@pytest.fixture
def mock_pipeline_results() -> dict:
    return {
        "emotion": [[
            {"label": "LABEL_25", "score": 0.85},
            {"label": "LABEL_19", "score": 0.3},
        ]],
        "crisis": [{"label": "NON_CRISIS", "score": 0.9}],
        "mental_health": [[{"label": "LABEL_0", "score": 0.75}]],
        "distortion": [],
    }


class TestMindLensFullPipeline:
    @pytest.mark.asyncio
    async def test_standard_flow_is_anonymized_before_models(
        self, mock_pipeline_results: dict
    ) -> None:
        orchestrator = Orchestrator()
        user_input = "My email is john@doe.com and I feel very down today."

        with patch.object(
            orchestrator.models,
            "predict_all",
            new=AsyncMock(return_value=mock_pipeline_results),
        ) as predict_all:
            result = await orchestrator.process_turn(user_input)

        model_input = predict_all.await_args.args[0]
        assert "[EMAIL]" in model_input
        assert "john@doe.com" not in model_input
        assert result["eos"]["surface_emotion"] == "sadness"
        assert result["crisis_flag"] is False
        assert "empathy" in result["agents"]

    @pytest.mark.asyncio
    async def test_regex_crisis_bypasses_all_models(self) -> None:
        orchestrator = Orchestrator()
        with patch.object(
            orchestrator.models, "predict_all", new=AsyncMock()
        ) as predict_all:
            result = await orchestrator.process_turn("I want to end my life right now")

        assert result["crisis_flag"] is True
        assert result["agents"] == ["crisis"]
        assert result["safety"]["layer_triggered"] == "regex"
        predict_all.assert_not_awaited()

    def test_anonymizer_removes_email(self) -> None:
        clean = anonymize("Contact me at john@doe.com")
        assert clean == "Contact me at [EMAIL]"
