"""Unit tests for the agent base system."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.agents.base_agent import (
    AgentContext,
    AgentOutput,
    AgentRegistry,
    BaseAgent,
    get_registry,
)
from app.core.emotional_os import EmotionalOperatingState


class DummyAgent(BaseAgent):
    """Concrete agent for testing the abstract base."""

    def __init__(self) -> None:
        super().__init__(
            name="dummy",
            description="A test agent",
            llm_tier="8B",
            max_tokens=50,
            always_runs=True,
        )

    async def run(self, ctx: AgentContext) -> AgentOutput:
        return AgentOutput(
            agent_name=self.name,
            text=f"Hello {ctx.user_name}",
            metadata={"test": True},
        )


class TestAgentOutput:
    """Validate AgentOutput dataclass."""

    def test_creation(self) -> None:
        output = AgentOutput(agent_name="test", text="hi")
        assert output.agent_name == "test"
        assert output.text == "hi"
        assert output.metadata == {}

    def test_immutable(self) -> None:
        output = AgentOutput(agent_name="test", text="hi")
        with pytest.raises(AttributeError):
            output.text = "changed"


class TestAgentContext:
    """Validate AgentContext dataclass."""

    def test_defaults(self) -> None:
        eos = EmotionalOperatingState()
        ctx = AgentContext(eos=eos, user_text="hello")
        assert ctx.user_name == "friend"
        assert ctx.session_history == []
        assert ctx.rag_chunks == []

    def test_with_rag(self) -> None:
        eos = EmotionalOperatingState()
        ctx = AgentContext(
            eos=eos,
            user_text="hello",
            rag_chunks=["chunk1", "chunk2"],
        )
        assert ctx.rag_chunks == ["chunk1", "chunk2"]


class TestBaseAgent:
    """Validate abstract base agent."""

    def test_init(self) -> None:
        agent = DummyAgent()
        assert agent.name == "dummy"
        assert agent.always_runs is True
        assert agent.max_tokens == 50

    @pytest.mark.asyncio
    async def test_run(self, agent_context: AgentContext) -> None:
        agent = DummyAgent()
        result = await agent.run(agent_context)
        assert result.agent_name == "dummy"
        assert "Hello Amiru" in result.text
        assert result.metadata["test"] is True

    def test_build_system_prompt(self, agent_context: AgentContext) -> None:
        agent = DummyAgent()
        prompt = agent._build_system_prompt(agent_context)
        assert "Dummy Agent" in prompt or "dummy" in prompt.lower()
        assert "Amiru" in prompt
        assert "never diagnose" in prompt.lower()

    def test_build_user_prompt(self, agent_context: AgentContext) -> None:
        agent = DummyAgent()
        prompt = agent._build_user_prompt(agent_context)
        assert "User said:" in prompt
        assert "anxious" in prompt

    def test_inject_rag(self, agent_context: AgentContext) -> None:
        agent = DummyAgent()
        base = "Base prompt"
        prompt = agent._inject_rag(base, agent_context)
        assert prompt == base  # No RAG chunks in fixture

        ctx_with_rag = AgentContext(
            eos=agent_context.eos,
            user_text="test",
            rag_chunks=["Clinical knowledge: CBT helps anxiety."],
        )
        prompt_with_rag = agent._inject_rag(base, ctx_with_rag)
        assert "Clinical knowledge" in prompt_with_rag


class TestAgentRegistry:
    """Validate agent registry."""

    def test_register_and_get(self) -> None:
        registry = AgentRegistry()
        agent = DummyAgent()
        registry.register(agent)
        assert registry.get("dummy") is agent

    def test_get_missing(self) -> None:
        registry = AgentRegistry()
        assert registry.get("nonexistent") is None

    def test_list_names(self) -> None:
        registry = AgentRegistry()
        registry.register(DummyAgent())
        assert "dummy" in registry.list_names()

    @pytest.mark.asyncio
    async def test_run_agent(self, agent_context: AgentContext) -> None:
        registry = AgentRegistry()
        registry.register(DummyAgent())
        result = await registry.run_agent("dummy", agent_context)
        assert result is not None
        assert result.agent_name == "dummy"

    @pytest.mark.asyncio
    async def test_run_agent_missing(self, agent_context: AgentContext) -> None:
        registry = AgentRegistry()
        result = await registry.run_agent("missing", agent_context)
        assert result is None

    @pytest.mark.asyncio
    async def test_run_agent_failure(self, agent_context: AgentContext) -> None:
        registry = AgentRegistry()
        failing = MagicMock(spec=BaseAgent)
        failing.name = "failing"
        failing.run = AsyncMock(side_effect=RuntimeError("boom"))
        registry.register(failing)  # type: ignore[arg-type]
        result = await registry.run_agent("failing", agent_context)
        assert result is None


class TestGlobalRegistry:
    """Validate module-level singleton."""

    def test_singleton(self) -> None:
        r1 = get_registry()
        r2 = get_registry()
        assert r1 is r2
