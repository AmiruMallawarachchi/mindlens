"""
MindLens Agent Base System
===========================
Defines the shared type system, abstract base class, and result
structures used by all 14 therapeutic agents.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.core.emotional_os import EmotionalOperatingState
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Agent output types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AgentOutput:
    """
    Immutable result from a single agent invocation.
    """

    agent_name: str
    text: str  # The generated response fragment
    metadata: dict[str, Any] = field(default_factory=dict)
    # e.g. {"llm_tier": "8B", "tokens_used": 45, "latency_ms": 320}


@dataclass
class AgentContext:
    """
    Context passed to every agent on every turn.
    """

    eos: EmotionalOperatingState
    user_text: str  # Anonymised user message
    user_name: str = "friend"
    session_history: list[dict[str, Any]] = field(default_factory=list)
    # last 3 turns for context window
    rag_chunks: list[str] = field(default_factory=list)
    # Retrieved clinical knowledge from ChromaDB


# ---------------------------------------------------------------------------
# Abstract base agent
# ---------------------------------------------------------------------------

class BaseAgent(ABC):
    """
    Every therapeutic agent inherits from this.
    """

    def __init__(
        self,
        name: str,
        description: str,
        llm_tier: str = "8B",
        max_tokens: int = 200,
        always_runs: bool = False,
    ) -> None:
        self.name = name
        self.description = description
        self.llm_tier = llm_tier
        self.max_tokens = max_tokens
        self.always_runs = always_runs
        self.logger = get_logger(f"agent.{name}")

    @abstractmethod
    async def run(self, ctx: AgentContext) -> AgentOutput:
        """
        Execute the agent given the current context.
        Must be implemented by every concrete agent.
        """
        ...

    def _build_system_prompt(self, ctx: AgentContext) -> str:
        """
        Default system prompt builder. Agents may override.
        """
        base = (
            f"You are the {self.name} of MindLens, a supportive AI mental health companion.\n"
            f"Your role: {self.description}\n"
            f"User's current emotional state: {ctx.eos.surface_emotion} "
            f"(distress: {ctx.eos.distress_level:.2f})\n"
            f"Active therapy modality: {ctx.eos.modality.value}\n"
            f"User's name: {ctx.user_name}\n"
            "IMPORTANT:\n"
            "- Never diagnose clinical conditions.\n"
            "- Never recommend medication.\n"
            "- Always be warm, supportive, and brief.\n"
            "- MindLens is not a clinical service.\n"
        )
        return base

    def _build_user_prompt(self, ctx: AgentContext) -> str:
        """
        Default user prompt. Agents usually override this.
        """
        return f"User said: {ctx.user_text}"

    def _inject_rag(self, prompt: str, ctx: AgentContext) -> str:
        """
        Append retrieved clinical knowledge to prompt if available.
        """
        if not ctx.rag_chunks:
            return prompt
        rag_text = "\n\n".join(ctx.rag_chunks)
        return f"{prompt}\n\nRelevant clinical knowledge:\n{rag_text}"


# ---------------------------------------------------------------------------
# Agent registry
# ---------------------------------------------------------------------------

class AgentRegistry:
    """
    Central registry for all agents. Allows the orchestrator to
    discover and dispatch agents by name.
    """

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        """Add an agent to the registry."""
        self._agents[agent.name] = agent
        logger.info("Registered agent: %s", agent.name)

    def get(self, name: str) -> BaseAgent | None:
        """Retrieve an agent by name."""
        return self._agents.get(name)

    def list_names(self) -> list[str]:
        """Return all registered agent names."""
        return list(self._agents.keys())

    async def run_agent(self, name: str, ctx: AgentContext) -> AgentOutput | None:
        """Execute a single agent by name."""
        agent = self.get(name)
        if agent is None:
            logger.warning("Agent not found: %s", name)
            return None
        try:
            return await agent.run(ctx)
        except Exception as exc:
            logger.exception("Agent %s failed: %s", name, exc)
            return None


# Singleton registry
_registry = AgentRegistry()


def get_registry() -> AgentRegistry:
    """Return the global agent registry."""
    return _registry
