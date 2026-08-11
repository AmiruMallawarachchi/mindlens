"""
CheckIn Scheduler
=================
Schedules the next pending_checkins entry (chat.py's `_send_pending_checkin`
delivers it on the user's next WebSocket connect).
No LLM calls. Background utility agent.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.agents.base_agent import AgentContext, AgentOutput, BaseAgent
from app.utils.logger import get_logger

logger = get_logger(__name__)


class CheckInScheduler(BaseAgent):
    """
    Schedules future check-in jobs by writing scheduling metadata; the
    pending_checkins document itself is written by the chat router
    (`_save_pending_checkin`) from this output.
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
        Return scheduling metadata. The actual pending_checkins write happens
        in the chat router after this output (`_save_pending_checkin`).
        """
        # Distress sets how urgent a check-in is...
        if ctx.eos.distress_level >= 0.7:
            hours_until = 4  # High distress → check in soon
        elif ctx.eos.distress_level >= 0.5:
            hours_until = 12
        else:
            hours_until = 24

        scheduled_at = datetime.utcnow() + timedelta(hours=hours_until)

        # ...but onboarding step 3 (morning/evening/whenever) says *when in
        # the day* it should land, and until now nothing read that back — every
        # check-in used the distress-only offset regardless of what the user
        # picked. High distress still overrides straight to `hours_until`
        # above; the preference only nudges the clock-time for calmer turns.
        preferred = ctx.eos.checkin_preferred_time
        if preferred in ("morning", "evening") and ctx.eos.distress_level < 0.7:
            target_hour = 8 if preferred == "morning" else 19
            candidate = scheduled_at.replace(hour=target_hour, minute=0, second=0, microsecond=0)
            if candidate <= datetime.utcnow():
                candidate += timedelta(days=1)
            scheduled_at = candidate

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
