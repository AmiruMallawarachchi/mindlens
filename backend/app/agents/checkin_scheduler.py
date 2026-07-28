"""
CheckIn Scheduler
=================
Schedules proactive check-in messages via APScheduler.
No LLM calls. Background utility agent.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.agents.base_agent import AgentContext, AgentOutput, BaseAgent
from app.utils.logger import get_logger

logger = get_logger(__name__)


class CheckInScheduler(BaseAgent):
    """
    Schedules future check-in jobs in the APScheduler job store.
    Does not generate user-facing text directly.
    """

    def __init__(self) -> None:
        super().__init__(
            name="checkin_scheduler",
            description="Schedule future check-in reminders",
            llm_tier="none",
            max_tokens=0,
            always_runs=False,
        )

    async def run(self, ctx: AgentContext) -> AgentOutput:
        """
        Return scheduling metadata. The actual APScheduler job
        creation happens in the session router after this output.
        """
        # Calculate next check-in time based on distress
        if ctx.eos.distress_level >= 0.7:
            hours_until = 4  # High distress → check in soon
        elif ctx.eos.distress_level >= 0.5:
            hours_until = 12
        else:
            hours_until = 24

        scheduled_at = datetime.utcnow() + timedelta(hours=hours_until)

        return AgentOutput(
            agent_name=self.name,
            text="",  # No user-facing text
            metadata={
                "llm_tier": "none",
                "scheduled_at": scheduled_at.isoformat(),
                "hours_until": hours_until,
                "action": "schedule_checkin",
            },
        )
