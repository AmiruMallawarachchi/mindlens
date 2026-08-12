"""Unit tests for the response assembler."""

from __future__ import annotations

import pytest
from app.agents.base_agent import AgentOutput
from app.agents.response_assembler import ResponseAssembler, assemble


class TestResponseAssembler:
    """Validate response assembly logic."""

    @pytest.fixture
    def assembler(self) -> ResponseAssembler:
        return ResponseAssembler()

    def test_empty_outputs_returns_fallback(self, assembler: ResponseAssembler) -> None:
        text = assembler.assemble([], user_name="Ravi")
        assert "Ravi" in text
        assert "MindLens is not a clinical service" in text

    def test_single_output(self, assembler: ResponseAssembler) -> None:
        outputs = [AgentOutput(agent_name="empathy", text="I hear you.")]
        text = assembler.assemble(outputs, user_name="Ravi")
        assert "I hear you." in text
        assert "MindLens is not a clinical service" in text

    def test_multiple_outputs_ordered(self, assembler: ResponseAssembler) -> None:
        outputs = [
            AgentOutput(agent_name="challenge", text="What evidence?"),
            AgentOutput(agent_name="empathy", text="I hear you."),
            AgentOutput(agent_name="mindfulness", text="Breathe."),
        ]
        text = assembler.assemble(outputs, user_name="Ravi")
        # Empathy should come before mindfulness, which comes before challenge
        empathy_pos = text.index("I hear you.")
        mindfulness_pos = text.index("Breathe.")
        challenge_pos = text.index("What evidence?")
        assert empathy_pos < mindfulness_pos < challenge_pos

    def test_deduplicates_duplicates(self, assembler: ResponseAssembler) -> None:
        outputs = [
            AgentOutput(agent_name="empathy", text="I hear you."),
            AgentOutput(agent_name="reflection", text="I hear you."),
        ]
        text = assembler.assemble(outputs, user_name="Ravi")
        # Should only appear once
        assert text.count("I hear you.") == 1

    def test_crisis_mode_exclusive(self, assembler: ResponseAssembler) -> None:
        outputs = [
            AgentOutput(agent_name="crisis", text="Please call 1926."),
            AgentOutput(agent_name="empathy", text="I hear you."),
        ]
        text = assembler.assemble(outputs, in_crisis=True, user_name="Ravi")
        assert "1926" in text
        assert "NIMH" in text
        assert "I hear you." not in text  # Non-crisis agents excluded
        assert "URGENT SUPPORT" in text

    def test_crisis_fallback_when_no_crisis_output(self, assembler: ResponseAssembler) -> None:
        outputs = []
        text = assembler.assemble(outputs, in_crisis=True, user_name="Ravi")
        assert "NIMH" in text
        assert "1926" in text

    def test_disclaimer_always_present(self, assembler: ResponseAssembler) -> None:
        outputs = [AgentOutput(agent_name="empathy", text="Hi.")]
        text = assembler.assemble(outputs, user_name="Ravi")
        assert "MindLens is not a clinical service" in text

    def test_crisis_disclaimer(self, assembler: ResponseAssembler) -> None:
        outputs = [AgentOutput(agent_name="crisis", text="Help.")]
        text = assembler.assemble(outputs, in_crisis=True, user_name="Ravi")
        # Crisis mode doesn't append the standard disclaimer,
        # it appends crisis resources instead
        assert "URGENT SUPPORT" in text

    def test_skips_empty_text(self, assembler: ResponseAssembler) -> None:
        outputs = [
            AgentOutput(agent_name="empathy", text="I hear you."),
            AgentOutput(agent_name="checkin_scheduler", text=""),
        ]
        text = assembler.assemble(outputs, user_name="Ravi")
        assert "checkin_scheduler" not in text


class TestAssembleConvenience:
    """Test the module-level convenience function."""

    def test_convenience_function(self) -> None:
        outputs = [AgentOutput(agent_name="empathy", text="Hello.")]
        text = assemble(outputs, user_name="Test")
        assert "Hello." in text
