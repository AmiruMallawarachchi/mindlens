"""Unit tests for Session Memory Save."""

from __future__ import annotations

from datetime import datetime

import pytest
from app.agents.base_agent import AgentContext
from app.agents.session_memory_save import SessionMemorySave
from app.core.emotional_os import EmotionalOperatingState


class TestSessionMemorySave:
    """Validate session memory save utility agent."""

    @pytest.fixture
    def agent(self) -> SessionMemorySave:
        return SessionMemorySave()

    @pytest.mark.asyncio
    async def test_no_llm(self, agent: SessionMemorySave, agent_context: EmotionalOperatingState) -> None:
        assert agent.llm_tier == "none"
        assert agent.max_tokens == 0

    @pytest.mark.asyncio
    async def test_returns_metadata(self, agent: SessionMemorySave, agent_context: EmotionalOperatingState) -> None:
        result = await agent.run(agent_context)
        assert result.agent_name == "session_memory_save"
        assert result.text == ""
        assert result.metadata["action"] == "save_turn"
        assert "session_id" in result.metadata
        assert "surface_emotion" in result.metadata
        assert "distress_level" in result.metadata
        assert "modality" in result.metadata
        assert "timestamp" in result.metadata
        assert "extracted" in result.metadata

    @pytest.mark.asyncio
    async def test_timestamp_is_iso(self, agent: SessionMemorySave, agent_context: EmotionalOperatingState) -> None:
        result = await agent.run(agent_context)
        ts = result.metadata["timestamp"]
        # Should be a valid ISO timestamp
        parsed = datetime.fromisoformat(ts)
        assert parsed.year == datetime.now().year


class TestMemoryExtraction:
    """Regression — before this, `user_memory` was fully readable/editable
    but nothing ever wrote to it from an ordinary conversation: "What's been
    hard" / "What's helped" could only be filled by an admin-only endpoint,
    and a new person only through onboarding. This is the extraction that
    makes the Memory page's promise ("mentioning something makes it show up
    here") actually true."""

    @pytest.fixture
    def agent(self) -> SessionMemorySave:
        return SessionMemorySave()

    @staticmethod
    def _ctx(text: str, **eos_kwargs: object) -> AgentContext:
        return AgentContext(
            eos=EmotionalOperatingState(**eos_kwargs),
            user_text=text,
            user_name="Amiru",
        )

    @pytest.mark.asyncio
    async def test_extracts_a_person_forward_order(self, agent: SessionMemorySave) -> None:
        """'My sister Amaya' — capitalised at the start of a sentence, which
        a case-sensitive match on 'my' would have missed entirely."""
        ctx = self._ctx("My sister Amaya called me today and it was nice.")
        result = await agent.run(ctx)
        assert result.metadata["extracted"]["person_relation"] == "sister"
        assert result.metadata["extracted"]["person_name"] == "Amaya"

    @pytest.mark.asyncio
    async def test_person_name_casing_is_normalized(self, agent: SessionMemorySave) -> None:
        """"AMAYA" and "amaya" must collapse to the same `people` key as
        "Amaya" — otherwise the same person shows up multiple times on the
        Memory page depending on how a message happened to capitalize them."""
        ctx = self._ctx("My sister AMAYA called today.")
        result = await agent.run(ctx)
        assert result.metadata["extracted"]["person_name"] == "Amaya"

    @pytest.mark.asyncio
    async def test_extracts_a_person_reverse_order(self, agent: SessionMemorySave) -> None:
        ctx = self._ctx("Amaya, my sister, called me today")
        result = await agent.run(ctx)
        assert result.metadata["extracted"]["person_relation"] == "sister"
        assert result.metadata["extracted"]["person_name"] == "Amaya"

    @pytest.mark.asyncio
    async def test_extracts_a_hard_topic_on_a_negative_turn(self, agent: SessionMemorySave) -> None:
        ctx = self._ctx("I feel anxious about my exam tomorrow.", valence="negative")
        result = await agent.run(ctx)
        assert result.metadata["extracted"]["trigger_topic"] == "exams"

    @pytest.mark.asyncio
    async def test_does_not_flag_a_topic_mentioned_calmly(self, agent: SessionMemorySave) -> None:
        """A topic keyword alone isn't enough — "exams are done, I'm
        relieved" shouldn't get filed under "what's been hard"."""
        ctx = self._ctx(
            "My exams are finally done and I feel relieved.",
            distress_level=0.2,
            valence="positive",
        )
        result = await agent.run(ctx)
        assert "trigger_topic" not in result.metadata["extracted"]

    @pytest.mark.asyncio
    async def test_extracts_coping_only_with_a_helped_phrase(self, agent: SessionMemorySave) -> None:
        ctx = self._ctx("Going for a walk really helped me calm down.")
        result = await agent.run(ctx)
        assert result.metadata["extracted"]["effective_coping"] == "going for a walk"

    @pytest.mark.asyncio
    async def test_mentioning_an_activity_without_helped_extracts_nothing(
        self, agent: SessionMemorySave
    ) -> None:
        """The keyword alone isn't a coping strategy — only pairing it with
        a "helped" phrase counts, otherwise "I went for a walk and then had
        a huge fight" would get filed as something that helped."""
        ctx = self._ctx("I went for a walk earlier.")
        result = await agent.run(ctx)
        assert "effective_coping" not in result.metadata["extracted"]

    @pytest.mark.asyncio
    async def test_ordinary_turn_extracts_nothing(self, agent: SessionMemorySave) -> None:
        ctx = self._ctx("nothing interesting happened today")
        result = await agent.run(ctx)
        assert result.metadata["extracted"] == {}

    @pytest.mark.asyncio
    async def test_memory_depth_nothing_disables_extraction(self, agent: SessionMemorySave) -> None:
        """Settings > Memory depth = Nothing also stops new memory from
        accumulating, not just recall — see emotional_os.py's field doc."""
        ctx = self._ctx(
            "My sister Amaya called, my exam went badly, a walk helped.",
            memory_depth="nothing",
            valence="negative",
        )
        result = await agent.run(ctx)
        assert result.metadata["extracted"] == {}
