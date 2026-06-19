"""Unit tests for Orchestrator EOS builder and routing."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.agents.orchestrator import Orchestrator
from app.core.emotional_os import EmotionalOperatingState, Modality


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
        assert "TestUser" in result["assembled_text"] or "MindLens is not a clinical service" in result["assembled_text"]

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


class TestOrchestratorAgentRouting:
    """Validate the expanded _select_agents method."""

    def test_empathy_always_present(self) -> None:
        eos = EmotionalOperatingState()
        agents = Orchestrator._select_agents(eos, crisis_flag=False)
        assert "empathy" in agents

    def test_crisis_override(self) -> None:
        eos = EmotionalOperatingState()
        agents = Orchestrator._select_agents(eos, crisis_flag=True)
        assert agents == ["crisis"]

    def test_mindfulness_for_high_distress(self) -> None:
        eos = EmotionalOperatingState(distress_level=0.6)
        agents = Orchestrator._select_agents(eos, crisis_flag=False)
        assert "mindfulness" in agents

    def test_music_for_distress(self) -> None:
        eos = EmotionalOperatingState(distress_level=0.5)
        agents = Orchestrator._select_agents(eos, crisis_flag=False)
        assert "music" in agents

    def test_challenge_gated_by_trust(self) -> None:
        eos = EmotionalOperatingState(trust_level=0.7, emotional_stability=0.6, distress_level=0.4)
        agents = Orchestrator._select_agents(eos, crisis_flag=False)
        assert "challenge" in agents

    def test_challenge_blocked_low_trust(self) -> None:
        eos = EmotionalOperatingState(trust_level=0.3, emotional_stability=0.6)
        agents = Orchestrator._select_agents(eos, crisis_flag=False)
        assert "challenge" not in agents

    def test_distortion_for_cbt(self) -> None:
        eos = EmotionalOperatingState(modality=Modality.CBT)
        agents = Orchestrator._select_agents(eos, crisis_flag=False)
        assert "distortion" in agents

    def test_distortion_blocked_for_dbt(self) -> None:
        eos = EmotionalOperatingState(modality=Modality.DBT)
        agents = Orchestrator._select_agents(eos, crisis_flag=False)
        assert "distortion" not in agents

    def test_routine_for_fatigue(self) -> None:
        eos = EmotionalOperatingState(mental_fatigue=0.8)
        agents = Orchestrator._select_agents(eos, crisis_flag=False)
        assert "routine" in agents

    def test_journaling_gated(self) -> None:
        from app.core.emotional_os import Receptiveness
        eos = EmotionalOperatingState(
            emotional_stability=0.5,
            mental_fatigue=0.5,
            receptiveness=Receptiveness(journaling=0.7),
        )
        agents = Orchestrator._select_agents(eos, crisis_flag=False)
        assert "journaling" in agents

    def test_progress_every_5_turns(self) -> None:
        eos = EmotionalOperatingState(session_turn_count=5)
        agents = Orchestrator._select_agents(eos, crisis_flag=False)
        assert "progress" in agents

    def test_personality_after_turn_2(self) -> None:
        eos = EmotionalOperatingState(session_turn_count=3)
        agents = Orchestrator._select_agents(eos, crisis_flag=False)
        assert "personality" in agents

    def test_session_memory_save_always(self) -> None:
        eos = EmotionalOperatingState()
        agents = Orchestrator._select_agents(eos, crisis_flag=False)
        assert "session_memory_save" in agents

    def test_checkin_scheduler_every_3_turns(self) -> None:
        eos = EmotionalOperatingState(session_turn_count=3)
        agents = Orchestrator._select_agents(eos, crisis_flag=False)
        assert "checkin_scheduler" in agents

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
