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
    orch._retriever = MagicMock()
    orch._retriever.retrieve.return_value = []
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
        eos = EmotionalOperatingState(distress_level=0.6, session_turn_count=3)
        agents = Orchestrator._select_agents(eos, crisis_flag=False)
        assert "mindfulness" in agents

    def test_music_for_distress(self) -> None:
        eos = EmotionalOperatingState(distress_level=0.5)
        agents = Orchestrator._select_agents(eos, crisis_flag=False)
        assert "music" in agents

    def test_challenge_gated_by_trust(self) -> None:
        eos = EmotionalOperatingState(
            trust_level=0.7, emotional_stability=0.6, distress_level=0.4, session_turn_count=3
        )
        agents = Orchestrator._select_agents(eos, crisis_flag=False)
        assert "challenge" in agents

    def test_challenge_blocked_low_trust(self) -> None:
        eos = EmotionalOperatingState(trust_level=0.3, emotional_stability=0.6)
        agents = Orchestrator._select_agents(eos, crisis_flag=False)
        assert "challenge" not in agents

    def test_distortion_for_cbt(self) -> None:
        eos = EmotionalOperatingState(modality=Modality.CBT, session_turn_count=3)
        agents = Orchestrator._select_agents(eos, crisis_flag=False)
        assert "distortion" in agents

    def test_opening_turn_lets_empathy_ask_alone(self) -> None:
        """The wall-of-text complaint. On turn one empathy asks what's
        going on; a specialist firing alongside it answers a question the
        user hasn't replied to yet. Someone who said they were putting off
        their project got a five-step grounding script in the same breath
        as "what's holding you back?"."""
        eos = EmotionalOperatingState(
            session_turn_count=0,
            distress_level=0.6,
            core_emotion="nervousness",
            modality=Modality.CBT,
            trust_level=0.9,
            emotional_stability=0.9,
            mental_fatigue=0.9,
            session_depth=0.9,
        )
        agents = Orchestrator._select_agents(eos, crisis_flag=False)
        assert "empathy" in agents
        for prescriptive in (
            "mindfulness", "reflection", "challenge",
            "distortion", "routine", "journaling",
        ):
            assert prescriptive not in agents, f"{prescriptive} spoke on turn one"

    def test_opening_turn_yields_to_high_distress(self) -> None:
        """Conversational shape never outranks grounding someone who is
        genuinely struggling."""
        eos = EmotionalOperatingState(
            session_turn_count=0, distress_level=0.8, core_emotion="anxiety"
        )
        agents = Orchestrator._select_agents(eos, crisis_flag=False)
        assert "mindfulness" in agents

    def test_distortion_blocked_for_dbt(self) -> None:
        eos = EmotionalOperatingState(modality=Modality.DBT)
        agents = Orchestrator._select_agents(eos, crisis_flag=False)
        assert "distortion" not in agents

    def test_routine_for_fatigue(self) -> None:
        eos = EmotionalOperatingState(mental_fatigue=0.8, session_turn_count=3)
        agents = Orchestrator._select_agents(eos, crisis_flag=False)
        assert "routine" in agents

    def test_journaling_gated(self) -> None:
        from app.core.emotional_os import Receptiveness
        eos = EmotionalOperatingState(
            emotional_stability=0.5,
            mental_fatigue=0.5,
            receptiveness=Receptiveness(journaling=0.7),
            session_turn_count=3,
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


class TestIntrovertScoreApplication:
    """T2 — the stored social profile reaches the EOS, except in crisis."""

    MEMORY = {"preferences": {"introvert_score": 0.2}}

    @pytest.mark.asyncio
    async def test_stored_score_is_applied_on_a_normal_turn(
        self, orchestrator: Orchestrator, mock_model_manager: MagicMock
    ) -> None:
        orchestrator.models = mock_model_manager
        result = await orchestrator.run_full_pipeline(
            "I feel anxious", user_name="Amiru", memory=self.MEMORY
        )
        assert result["crisis_flag"] is False
        assert result["eos"]["introvert_score"] == 0.2

    @pytest.mark.asyncio
    async def test_crisis_turn_does_not_apply_the_stored_score(
        self, orchestrator: Orchestrator
    ) -> None:
        """A crisis reply comes from vetted templates; nothing on the user's
        profile may reshape it. Same rule as the style preferences."""
        orchestrator.models.predict_all = AsyncMock(return_value={
            "emotion": [[{"label": "LABEL_25", "score": 0.9}]],
            "crisis": [{"label": "CRISIS", "score": 0.85}],
            "mental_health": [[{"label": "LABEL_1", "score": 0.5}]],
        })
        result = await orchestrator.run_full_pipeline(
            "suicidal text", user_name="Amiru", memory=self.MEMORY
        )
        assert result["crisis_flag"] is True
        assert result["eos"]["introvert_score"] == 0.5, "crisis turn inherited the profile"

    @pytest.mark.asyncio
    async def test_absent_score_leaves_the_default_untouched(
        self, orchestrator: Orchestrator, mock_model_manager: MagicMock
    ) -> None:
        orchestrator.models = mock_model_manager
        result = await orchestrator.run_full_pipeline(
            "I feel anxious", user_name="Amiru", memory={"preferences": {}}
        )
        assert result["eos"]["introvert_score"] == 0.5


class TestTonePreferenceApplication:
    """Regression — Settings > General > Tone saved and round-tripped
    correctly but the orchestrator never assigned it onto the EOS, so
    empathy_agent's tone_instruction branch (which reads eos.tone_preference)
    never saw it. Gentle/Balanced/Direct changed nothing about the reply."""

    MEMORY = {"preferences": {"tone_preference": "direct"}}

    @pytest.mark.asyncio
    async def test_stored_tone_is_applied_on_a_normal_turn(
        self, orchestrator: Orchestrator, mock_model_manager: MagicMock
    ) -> None:
        orchestrator.models = mock_model_manager
        result = await orchestrator.run_full_pipeline(
            "I feel anxious", user_name="Amiru", memory=self.MEMORY
        )
        assert result["crisis_flag"] is False
        assert result["eos"]["tone_preference"] == "direct"

    @pytest.mark.asyncio
    async def test_crisis_turn_does_not_apply_the_stored_tone(
        self, orchestrator: Orchestrator
    ) -> None:
        """Same rule as personality/custom_instructions: a crisis reply comes
        from vetted templates and must not be restyled by a saved preference."""
        orchestrator.models.predict_all = AsyncMock(return_value={
            "emotion": [[{"label": "LABEL_25", "score": 0.9}]],
            "crisis": [{"label": "CRISIS", "score": 0.85}],
            "mental_health": [[{"label": "LABEL_1", "score": 0.5}]],
        })
        result = await orchestrator.run_full_pipeline(
            "suicidal text", user_name="Amiru", memory=self.MEMORY
        )
        assert result["crisis_flag"] is True
        assert result["eos"]["tone_preference"] == "balanced", (
            "crisis turn inherited the saved tone"
        )

    @pytest.mark.asyncio
    async def test_absent_tone_leaves_the_default_untouched(
        self, orchestrator: Orchestrator, mock_model_manager: MagicMock
    ) -> None:
        orchestrator.models = mock_model_manager
        result = await orchestrator.run_full_pipeline(
            "I feel anxious", user_name="Amiru", memory={"preferences": {}}
        )
        assert result["eos"]["tone_preference"] == "balanced"


class TestSessionTurnCountIsPopulated:
    """Regression — three agents were gated behind a field nothing ever set.

    `session_turn_count` was read in `_select_agents` but assigned nowhere in
    `app/`, so it was 0 on every real turn and personality (>2), progress
    (every 5) and checkin_scheduler (every 3) could never be selected. The
    existing tests missed it because they constructed the EOS by hand with a
    non-zero count — the only place in the repo it was ever set.
    """

    @pytest.mark.asyncio
    async def test_turn_count_comes_from_session_history(
        self, orchestrator: Orchestrator, mock_model_manager: MagicMock
    ) -> None:
        orchestrator.models = mock_model_manager
        history = [{"role": "user", "text": f"turn {i}"} for i in range(6)]
        result = await orchestrator.run_full_pipeline(
            "I feel anxious", user_name="Amiru", session_history=history
        )
        assert result["eos"]["session_turn_count"] == 6

    @pytest.mark.asyncio
    async def test_personality_agent_is_reachable_on_a_real_turn(
        self, orchestrator: Orchestrator, mock_model_manager: MagicMock
    ) -> None:
        """The gate is `> 2`; a fresh session must not select it, a
        continuing one must."""
        orchestrator.models = mock_model_manager

        early = await orchestrator.run_full_pipeline(
            "I feel anxious",
            user_name="Amiru",
            session_history=[{"role": "user", "text": "hi"}],
        )
        assert "personality" not in early["agents"]

        later = await orchestrator.run_full_pipeline(
            "I feel anxious",
            user_name="Amiru",
            session_history=[{"role": "user", "text": f"t{i}"} for i in range(5)],
        )
        assert "personality" in later["agents"], (
            "PersonalityAgent still unreachable — the personality loop is dead"
        )

    @pytest.mark.asyncio
    async def test_empty_history_is_turn_zero(
        self, orchestrator: Orchestrator, mock_model_manager: MagicMock
    ) -> None:
        orchestrator.models = mock_model_manager
        result = await orchestrator.run_full_pipeline("hi", session_history=[])
        assert result["eos"]["session_turn_count"] == 0

    @pytest.mark.asyncio
    async def test_progress_and_checkin_gates_are_reachable(
        self, orchestrator: Orchestrator, mock_model_manager: MagicMock
    ) -> None:
        """Collateral of the same bug — both were equally unreachable."""
        orchestrator.models = mock_model_manager
        result = await orchestrator.run_full_pipeline(
            "I feel anxious",
            user_name="Amiru",
            session_history=[{"role": "user", "text": f"t{i}"} for i in range(15)],
        )
        assert result["eos"]["session_turn_count"] == 15
        assert "progress" in result["agents"]        # 15 % 5 == 0
        assert "checkin_scheduler" in result["agents"]  # 15 % 3 == 0
