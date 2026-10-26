"""Focused orchestrator tests for telemetry behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.agents.orchestrator import Orchestrator
from app.core.emotional_os import EmotionalOperatingState, Modality
from .orchestrator_fixtures import _stub_groq, mock_model_manager, orchestrator


class TestTurnTelemetry:
    """The reasoning trail must describe the turn, not assert a script.

    Before this, the safety verdict was computed and then dropped before
    transmission, RAG's status was never sent at all, and the UI printed
    "Working from CBT" on every turn including "hi" — because modality is set
    unconditionally even when nothing modality-driven ran.

    Groq is stubbed module-wide (see _stub_groq above) — no class-local
    override needed here any more.
    """

    @pytest.mark.asyncio
    async def test_trivial_turn_reports_rag_skipped_and_no_modality(
        self, orchestrator: Orchestrator, mock_model_manager: MagicMock
    ) -> None:
        orchestrator.models = mock_model_manager
        result = await orchestrator.run_full_pipeline("hi", user_name="TestUser")

        telemetry = result["telemetry"]

        # The gate and what it gates must agree. Asserting substantive is
        # False outright would be asserting the mock's distress score, not
        # the behaviour — distress deliberately overrides length, so a stub
        # that reports high distress makes "hi" substantive and should.
        if telemetry["substantive"]:
            assert telemetry["rag"]["status"] in {"ran", "failed", "provided"}
        else:
            assert telemetry["rag"]["status"] == "skipped_trivial"
            assert telemetry["rag"]["chunks"] == 0

        # No modality-driven agent runs on an opening "hi" either way, so
        # naming a modality would describe a decision that had no effect.
        assert telemetry["modality"] is None

    @pytest.mark.asyncio
    async def test_substantive_turn_reports_rag_status(
        self, orchestrator: Orchestrator, mock_model_manager: MagicMock
    ) -> None:
        orchestrator.models = mock_model_manager
        result = await orchestrator.run_full_pipeline(
            "I have been feeling really stressed about my final year project",
            user_name="TestUser",
        )
        # "provided" would mean the caller passed chunks in; from this entry
        # point it must genuinely have attempted retrieval.
        assert result["telemetry"]["rag"]["status"] in {"ran", "failed"}

    @pytest.mark.asyncio
    async def test_safety_verdict_survives_into_the_result(
        self, orchestrator: Orchestrator, mock_model_manager: MagicMock
    ) -> None:
        """It was computed and then dropped, which is why the client had to
        hardcode the sentence."""
        orchestrator.models = mock_model_manager
        result = await orchestrator.run_full_pipeline("hi", user_name="TestUser")
        assert "safety" in result
        assert "is_crisis" in result["safety"]

    @pytest.mark.asyncio
    async def test_rag_telemetry_names_the_reranker_model_when_it_ran(
        self, orchestrator: Orchestrator, mock_model_manager: MagicMock
    ) -> None:
        """The trail used to say "Pulled 5 passages" with no way to know
        which model did the ranking — the equivalent of Claude naming a tool
        it used without saying which one. When retrieval genuinely ran with
        reranking enabled, the model actually configured for it is named."""
        orchestrator.models = mock_model_manager
        with patch("app.agents.orchestrator.settings.rag_reranker_enabled", True):
            result = await orchestrator.run_full_pipeline(
                "I have been feeling really stressed about my final year project",
                user_name="TestUser",
            )
        rag = result["telemetry"]["rag"]
        if rag["status"] == "ran":
            assert rag["model"] == "mindlens-rag-reranker"

    @pytest.mark.asyncio
    async def test_rag_telemetry_names_no_model_when_reranking_disabled(
        self, orchestrator: Orchestrator, mock_model_manager: MagicMock
    ) -> None:
        """Naming a model that was configured off would claim work that
        didn't happen — rag_reranker_enabled=False must mean model=None
        even on a turn where retrieval itself ran fine."""
        orchestrator.models = mock_model_manager
        with patch("app.agents.orchestrator.settings.rag_reranker_enabled", False):
            result = await orchestrator.run_full_pipeline(
                "I have been feeling really stressed about my final year project",
                user_name="TestUser",
            )
        assert result["telemetry"]["rag"]["model"] is None

    @pytest.mark.asyncio
    async def test_rag_telemetry_names_no_model_when_skipped_or_failed(
        self, orchestrator: Orchestrator, mock_model_manager: MagicMock
    ) -> None:
        orchestrator.models = mock_model_manager
        result = await orchestrator.run_full_pipeline("hi", user_name="TestUser")
        rag = result["telemetry"]["rag"]
        if rag["status"] != "ran":
            assert rag["model"] is None

class TestStageCallback:
    """The pipeline used to run to completion before anything streamed —
    the client received all four trail sections at once, already finished,
    so there was no "one by one" to watch. on_stage fires as each stage
    genuinely completes so the client can show real, not staged, progress.
    """

    @pytest.mark.asyncio
    async def test_stages_fire_in_pipeline_order(
        self, orchestrator: Orchestrator, mock_model_manager: MagicMock
    ) -> None:
        orchestrator.models = mock_model_manager
        seen: list[str] = []

        async def on_stage(stage: str, detail: str) -> None:
            seen.append(stage)
            assert isinstance(detail, str) and detail

        await orchestrator.run_full_pipeline(
            "I have been feeling really stressed about my final year project",
            user_name="TestUser",
            on_stage=on_stage,
        )

        assert seen == ["safety", "reading", "memory", "retrieval", "approach"]

    @pytest.mark.asyncio
    async def test_crisis_still_announces_safety_and_reading(
        self, orchestrator: Orchestrator, mock_model_manager: MagicMock
    ) -> None:
        """Crisis skips memory/retrieval/agent-selection stages entirely, but
        the two that ran before the crisis check must still be reported —
        the trail must not go silent on the turn where honesty matters most."""
        orchestrator.models.predict_all = AsyncMock(return_value={
            "emotion": [[{"label": "LABEL_25", "score": 0.9}]],
            "crisis": [{"label": "CRISIS", "score": 0.85}],
            "mental_health": [[{"label": "LABEL_1", "score": 0.5}]],
        })
        seen: list[str] = []

        async def on_stage(stage: str, detail: str) -> None:
            seen.append(stage)

        await orchestrator.run_full_pipeline(
            "suicidal text", user_name="TestUser", on_stage=on_stage
        )

        assert "safety" in seen
        assert "reading" in seen

    @pytest.mark.asyncio
    async def test_no_callback_is_a_no_op_not_an_error(
        self, orchestrator: Orchestrator, mock_model_manager: MagicMock
    ) -> None:
        """Every existing caller omits on_stage — it must default to doing
        nothing, not raise, or every non-streaming caller breaks."""
        orchestrator.models = mock_model_manager
        result = await orchestrator.run_full_pipeline("hi", user_name="TestUser")
        assert "assembled_text" in result

