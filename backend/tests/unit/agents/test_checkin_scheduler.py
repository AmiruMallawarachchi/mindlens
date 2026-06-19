"""Unit tests for CheckIn Scheduler."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from app.agents.checkin_scheduler import CheckInScheduler
from app.core.emotional_os import EmotionalOperatingState


class TestCheckInScheduler:
    """Validate check-in scheduler utility agent."""

    @pytest.fixture
    def agent(self) -> CheckInScheduler:
        return CheckInScheduler()

    @pytest.mark.asyncio
    async def test_no_llm(self, agent: CheckInScheduler, agent_context: EmotionalOperatingState) -> None:
        assert agent.llm_tier == "none"
        assert agent.max_tokens == 0

    @pytest.mark.asyncio
    async def test_schedules_checkin(self, agent: CheckInScheduler, agent_context: EmotionalOperatingState) -> None:
        result = await agent.run(agent_context)
        assert result.agent_name == "checkin_scheduler"
        assert result.text == ""
        assert result.metadata["action"] == "schedule_checkin"
        assert "scheduled_at" in result.metadata
        assert "hours_until" in result.metadata

    @pytest.mark.asyncio
    async def test_high_distress_short_interval(self, agent: CheckInScheduler) -> None:
        from app.agents.base_agent import AgentContext
        from app.core.emotional_os import EmotionalOperatingState
        eos = EmotionalOperatingState(distress_level=0.9)
        ctx = AgentContext(eos=eos, user_text="test", user_name="Test")
        result = await agent.run(ctx)
        assert result.metadata["hours_until"] == 4

    @pytest.mark.asyncio
    async def test_low_distress_long_interval(self, agent: CheckInScheduler) -> None:
        from app.agents.base_agent import AgentContext
        from app.core.emotional_os import EmotionalOperatingState
        eos = EmotionalOperatingState(distress_level=0.2)
        ctx = AgentContext(eos=eos, user_text="test", user_name="Test")
        result = await agent.run(ctx)
        assert result.metadata["hours_until"] == 24

    @pytest.mark.asyncio
    async def test_scheduled_at_is_future(self, agent: CheckInScheduler, agent_context: EmotionalOperatingState) -> None:
        result = await agent.run(agent_context)
        scheduled = datetime.fromisoformat(result.metadata["scheduled_at"])
        assert scheduled > datetime.utcnow()
        assert scheduled < datetime.utcnow() + timedelta(hours=25)
