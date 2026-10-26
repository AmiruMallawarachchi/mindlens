"""Focused orchestrator tests for routing behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.agents.orchestrator import Orchestrator
from app.core.emotional_os import EmotionalOperatingState, Modality
from .orchestrator_fixtures import _stub_groq, mock_model_manager, orchestrator


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

    def test_specialists_held_back_on_the_opening_turn(self) -> None:
        """Empathy opens alone: turn one asks what is going on rather than
        prescribing an exercise before the user has answered anything."""
        eos = EmotionalOperatingState(distress_level=0.5, session_turn_count=0)
        agents = Orchestrator._select_agents(eos, crisis_flag=False)
        assert "empathy" in agents
        # Always-runs bookkeeping agents (session_memory_save) are exempt;
        # what must not appear is a speaking specialist.
        assert "mindfulness" not in agents
        assert "distortion" not in agents
        assert "challenge" not in agents

    def test_filler_turn_gets_only_empathy(self) -> None:
        """A short, undistressed turn ("ok thanks") should not summon an
        exercise, even mid-conversation."""
        eos = EmotionalOperatingState(distress_level=0.2, session_turn_count=4)
        agents = Orchestrator._select_agents(eos, crisis_flag=False, substantive=False)
        assert "mindfulness" not in agents
        assert "distortion" not in agents
        assert "empathy" in agents

    def test_distress_overrides_the_substance_gate(self) -> None:
        """"i cant anymore" is three words and the most important turn in the
        conversation — length must never be what silences the pipeline."""
        from app.agents.orchestrator import turn_is_substantive

        assert turn_is_substantive("i cant anymore", 0.9) is True
        assert turn_is_substantive("hi", 0.1) is False
        assert turn_is_substantive("i have been really struggling lately", 0.1) is True

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

class TestMindfulnessIsNotEveryTurn:
    """Once the classifiers were fixed and began returning real labels, an
    unconditional anxiety trigger meant a guided breathing exercise on
    nearly every turn — the same script instead of the app getting to know
    the person. A mild anxious reading no longer summons one; genuine
    distress still always does."""

    def test_mild_anxiety_alone_does_not_trigger_an_exercise(self) -> None:
        eos = EmotionalOperatingState(
            core_emotion="anxiety", distress_level=0.2, session_turn_count=3
        )
        assert "mindfulness" not in Orchestrator._select_agents(eos, crisis_flag=False)

    def test_warm_anxiety_does_trigger(self) -> None:
        eos = EmotionalOperatingState(
            core_emotion="anxiety", distress_level=0.45, session_turn_count=3
        )
        assert "mindfulness" in Orchestrator._select_agents(eos, crisis_flag=False)

    def test_high_distress_always_triggers_regardless_of_label(self) -> None:
        """The safety arm is untouched: whatever the emotion label says,
        someone in real distress still gets grounded."""
        eos = EmotionalOperatingState(
            core_emotion="sadness", distress_level=0.8, session_turn_count=3
        )
        assert "mindfulness" in Orchestrator._select_agents(eos, crisis_flag=False)

