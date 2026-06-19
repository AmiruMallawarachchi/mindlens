"""
MindLens Agents Package
=======================
All 14 therapeutic agents plus infrastructure.
"""

from __future__ import annotations

from app.agents.base_agent import (
    AgentContext,
    AgentOutput,
    AgentRegistry,
    BaseAgent,
    get_registry,
)
from app.agents.challenge_agent import ChallengeAgent
from app.agents.checkin_agent import CheckInAgent
from app.agents.checkin_scheduler import CheckInScheduler
from app.agents.crisis_agent import CrisisAgent
from app.agents.distortion_agent import DistortionAgent
from app.agents.empathy_agent import EmpathyAgent
from app.agents.groq_client import GroqClient, get_groq_client
from app.agents.journaling_agent import JournalingAgent
from app.agents.mindfulness_agent import MindfulnessAgent
from app.agents.music_agent import MusicAgent
from app.agents.personality_agent import PersonalityAgent
from app.agents.progress_agent import ProgressAgent
from app.agents.reflection_agent import ReflectionAgent
from app.agents.response_assembler import ResponseAssembler, assemble
from app.agents.routine_agent import RoutineAgent
from app.agents.session_memory_save import SessionMemorySave

__all__ = [
    # Base
    "AgentContext",
    "AgentOutput",
    "BaseAgent",
    "AgentRegistry",
    "get_registry",
    # Infrastructure
    "GroqClient",
    "get_groq_client",
    "ResponseAssembler",
    "assemble",
    # Agents
    "EmpathyAgent",
    "MindfulnessAgent",
    "CrisisAgent",
    "ReflectionAgent",
    "ChallengeAgent",
    "DistortionAgent",
    "RoutineAgent",
    "JournalingAgent",
    "MusicAgent",
    "CheckInAgent",
    "ProgressAgent",
    "PersonalityAgent",
    "CheckInScheduler",
    "SessionMemorySave",
]
