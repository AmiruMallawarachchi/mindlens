"""Focused orchestrator tests for preferences behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.agents.orchestrator import Orchestrator
from app.core.emotional_os import EmotionalOperatingState, Modality
from .orchestrator_fixtures import _stub_groq, mock_model_manager, orchestrator


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

