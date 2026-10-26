"""MindLens orchestrator facade and agent registry setup."""

from __future__ import annotations

from app.agents.base_agent import get_registry
from app.config import settings  # preserve the established patch/import path
from app.agents.challenge_agent import ChallengeAgent
from app.agents.checkin_agent import CheckInAgent
from app.agents.checkin_scheduler import CheckInScheduler
from app.agents.crisis_agent import CrisisAgent
from app.agents.distortion_agent import DistortionAgent
from app.agents.empathy_agent import EmpathyAgent
from app.agents.journaling_agent import JournalingAgent
from app.agents.mindfulness_agent import MindfulnessAgent
from app.agents.personality_agent import PersonalityAgent
from app.agents.progress_agent import ProgressAgent
from app.agents.reflection_agent import ReflectionAgent
from app.agents.response_assembler import ResponseAssembler
from app.agents.routine_agent import RoutineAgent
from app.agents.safety_gate import safety_gate
from app.agents.session_memory_save import SessionMemorySave
from app.models.loader import ModelManager
from app.rag.retriever import get_retriever
from app.utils.logger import get_logger
from .orchestration.pipeline import OrchestratorPipelineMixin
from .orchestration.scoring import OrchestratorScoringMixin
from .orchestration.shared import StageCallback, turn_is_substantive
from .orchestration.turn import OrchestratorTurnMixin

logger = get_logger("app.agents.orchestrator")


class Orchestrator(OrchestratorPipelineMixin, OrchestratorTurnMixin, OrchestratorScoringMixin):
    """Compatibility facade wiring the legacy turn pipeline and agent registry."""

    def __init__(self) -> None:
        self.models = ModelManager()
        self._safety = safety_gate
        self._assembler = ResponseAssembler()
        self._retriever = get_retriever()
        self._init_registry()

    def _init_registry(self) -> None:
        """Register all 13 agents in the global registry."""
        registry = get_registry()
        if not registry.list_names():
            agents = [
                EmpathyAgent(),
                MindfulnessAgent(),
                CrisisAgent(),
                ReflectionAgent(),
                ChallengeAgent(),
                DistortionAgent(),
                RoutineAgent(),
                JournalingAgent(),
                CheckInAgent(),
                ProgressAgent(),
                PersonalityAgent(),
                CheckInScheduler(),
                SessionMemorySave(),
            ]
            for agent in agents:
                registry.register(agent)
            logger.info("Registered %d agents in orchestrator", len(agents))
