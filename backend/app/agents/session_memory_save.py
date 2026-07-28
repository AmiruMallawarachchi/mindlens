"""
Session Memory Save
===================
Persists the current turn to MongoDB after all agents have run.
No LLM calls. Background utility agent.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.agents.base_agent import AgentContext, AgentOutput, BaseAgent
from app.utils.logger import get_logger

logger = get_logger(__name__)


class SessionMemorySave(BaseAgent):
    """
    Saves the completed turn to the sessions collection in MongoDB.
    Updates the user_memory document with longitudinal data.
    """

    def __init__(self) -> None:
        super().__init__(
            name="session_memory_save",
            description="Persist session turn to MongoDB",
            llm_tier="none",
            max_tokens=0,
            always_runs=False,
        )

    async def run(self, ctx: AgentContext) -> AgentOutput:
        """
        Return save metadata. The actual DB write happens in the
        session router after this output.
        """
        return AgentOutput(
            agent_name=self.name,
            text="",  # No user-facing text
            metadata={
                "llm_tier": "none",
                "action": "save_turn",
                "session_id": ctx.eos.session_id,
                "surface_emotion": ctx.eos.surface_emotion,
                "distress_level": ctx.eos.distress_level,
                "modality": ctx.eos.modality.value,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )
