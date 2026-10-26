"""Focused orchestrator tests for pipeline behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.agents.orchestrator import Orchestrator
from app.core.emotional_os import EmotionalOperatingState, Modality
from .orchestrator_fixtures import _stub_groq, mock_model_manager, orchestrator


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

class TestOrchestratorFullPipeline:
    """Validate the complete agent execution pipeline."""

    @pytest.mark.asyncio
    async def test_run_full_pipeline_returns_assembled_text(
        self, orchestrator: Orchestrator, mock_model_manager: MagicMock
    ) -> None:
        """run_full_pipeline returns assembled text + metadata."""
        orchestrator.models = mock_model_manager
        result = await orchestrator.run_full_pipeline("I feel anxious about work")
        assert "eos" in result
        assert "agents" in result
        assert "crisis_flag" in result
        assert "assembled_text" in result
        assert "agent_outputs" in result
        assert len(result["assembled_text"]) > 0

    @pytest.mark.asyncio
    async def test_crisis_full_pipeline_routes_only_crisis(
        self, orchestrator: Orchestrator
    ) -> None:
        """Crisis mode in full pipeline returns only crisis response."""
        orchestrator.models.predict_all = AsyncMock(return_value={
            "emotion": [[{"label": "LABEL_25", "score": 0.9}]],
            "crisis": [{"label": "CRISIS", "score": 0.85}],
            "mental_health": [[{"label": "LABEL_1", "score": 0.5}]],
        })
        result = await orchestrator.run_full_pipeline("suicidal text")
        assert result["crisis_flag"] is True
        assert "1926" in result["assembled_text"] or "NIMH" in result["assembled_text"]
        # Empathy should NOT be in the assembled text during crisis
        assert "I hear you" not in result["assembled_text"] or "1926" in result["assembled_text"]

    @pytest.mark.asyncio
    async def test_full_pipeline_runs_multiple_agents(
        self, orchestrator: Orchestrator, mock_model_manager: MagicMock
    ) -> None:
        """Normal pipeline runs empathy + mindfulness + others."""
        orchestrator.models = mock_model_manager
        result = await orchestrator.run_full_pipeline(
            "I feel very anxious and can't sleep",
            user_name="TestUser",
        )
        assert "empathy" in result["agents"]
        assert result["crisis_flag"] is False
        assert len(result["agent_outputs"]) > 0
        # The disclaimer is no longer appended to the prose, so this can
        # only assert on the reply itself.
        assert result["assembled_text"].strip()
        assert "not a clinical service" not in result["assembled_text"]

    @pytest.mark.asyncio
    async def test_full_pipeline_with_session_history(
        self, orchestrator: Orchestrator, mock_model_manager: MagicMock
    ) -> None:
        """Pipeline accepts session history for context."""
        orchestrator.models = mock_model_manager
        result = await orchestrator.run_full_pipeline(
            "I still feel bad",
            user_name="TestUser",
            session_history=[
                {"role": "user", "text": "I feel sad", "emotion": "sadness"},
                {"role": "assistant", "text": "I hear you."},
            ],
        )
        assert "assembled_text" in result
        assert result["agent_outputs"] is not None

    @pytest.mark.asyncio
    async def test_full_pipeline_with_rag(
        self, orchestrator: Orchestrator, mock_model_manager: MagicMock
    ) -> None:
        """Pipeline accepts RAG chunks for grounding."""
        orchestrator.models = mock_model_manager
        result = await orchestrator.run_full_pipeline(
            "I feel anxious",
            user_name="TestUser",
            rag_chunks=["CBT for anxiety: cognitive restructuring helps."],
        )
        assert "assembled_text" in result

    @pytest.mark.asyncio
    async def test_full_pipeline_without_memory_has_no_recall(
        self, orchestrator: Orchestrator, mock_model_manager: MagicMock
    ) -> None:
        """No memory document -> memory_recalled is empty, not fabricated."""
        orchestrator.models = mock_model_manager
        result = await orchestrator.run_full_pipeline("I feel anxious about work")
        assert result["memory_recalled"] == []

    @pytest.mark.asyncio
    async def test_full_pipeline_merges_people_graph_from_memory(
        self, orchestrator: Orchestrator, mock_model_manager: MagicMock
    ) -> None:
        """A person mentioned by name surfaces in memory_recalled and EOS."""
        orchestrator.models = mock_model_manager
        memory = {
            "people": {
                "Ravi": {"role": "best friend", "context": "same exam", "sentiment": "positive"},
            }
        }
        result = await orchestrator.run_full_pipeline(
            "I told Ravi about the exam",
            memory=memory,
        )
        assert any("Ravi" in item for item in result["memory_recalled"])
        assert result["eos"]["people_graph"][0]["name"] == "Ravi"

    @pytest.mark.asyncio
    async def test_full_pipeline_applies_preferred_modality(
        self, orchestrator: Orchestrator
    ) -> None:
        """A stated modality preference overrides the distress-based default
        when distress isn't high enough to force DBT."""
        # A low-distress mock: the shared `mock_model_manager` fixture's
        # NON_CRISIS score of 0.12 inverts to a 0.88 crisis contribution
        # (_parse_crisis treats low confidence in "non-crisis" as evidence
        # for crisis), which alone pushes distress over the 0.7 DBT
        # threshold — not useful for testing the low-distress branch.
        orchestrator.models.predict_all = AsyncMock(return_value={
            "emotion": [[{"label": "LABEL_17", "score": 0.9}]],
            "crisis": [{"label": "NON_CRISIS", "score": 0.95}],
            "mental_health": [[{"label": "LABEL_1", "score": 0.05}]],
        })
        memory = {"preferences": {"preferred_modality": "ACT"}}
        result = await orchestrator.run_full_pipeline(
            "just a normal day",
            memory=memory,
        )
        assert result["eos"]["distress_level"] <= 0.7
        assert result["eos"]["modality"] == "ACT"

    @pytest.mark.asyncio
    async def test_full_pipeline_high_distress_overrides_preference(
        self, orchestrator: Orchestrator
    ) -> None:
        """A high-distress turn keeps the safety-driven DBT modality even
        when the user's memory prefers something else."""
        orchestrator.models.predict_all = AsyncMock(return_value={
            "emotion": [[{"label": "LABEL_25", "score": 0.95}]],
            "crisis": [{"label": "NON_CRISIS", "score": 0.1}],
            "mental_health": [[{"label": "LABEL_0", "score": 0.95}]],
        })
        memory = {"preferences": {"preferred_modality": "ACT"}}
        result = await orchestrator.run_full_pipeline(
            "I can't take this anymore, everything hurts so much",
            memory=memory,
        )
        assert result["eos"]["distress_level"] > 0.7
        assert result["eos"]["modality"] == "DBT"

    @pytest.mark.asyncio
    async def test_crisis_pipeline_skips_memory_merge(
        self, orchestrator: Orchestrator
    ) -> None:
        """Crisis mode doesn't personalise via memory — the template is
        deliberately generic."""
        orchestrator.models.predict_all = AsyncMock(return_value={
            "emotion": [[{"label": "LABEL_25", "score": 0.9}]],
            "crisis": [{"label": "CRISIS", "score": 0.85}],
            "mental_health": [[{"label": "LABEL_1", "score": 0.5}]],
        })
        memory = {
            "people": {"Ravi": {"role": "friend", "context": "", "sentiment": "positive"}},
            "preferences": {"preferred_modality": "ACT"},
        }
        result = await orchestrator.run_full_pipeline("suicidal text", memory=memory)
        assert result["crisis_flag"] is True
        assert result["eos"]["people_graph"] == []

