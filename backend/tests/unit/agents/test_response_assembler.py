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
        """Whoever speaks still speaks in priority order."""
        outputs = [
            AgentOutput(agent_name="mindfulness", text="Breathe."),
            AgentOutput(agent_name="empathy", text="I hear you."),
        ]
        text = assembler.assemble(outputs, user_name="Ravi")
        assert text.index("I hear you.") < text.index("Breathe.")

    def test_only_one_specialist_speaks(self, assembler: ResponseAssembler) -> None:
        """The wall-of-text bug: every speaking agent writes a complete
        conversational turn, so concatenating all of them produced three
        replies stapled together — an empathy greeting, then a CBT
        challenge, then a music pitch, at someone who had only said they
        wanted help. Empathy plus one specialist, no more."""
        outputs = [
            AgentOutput(agent_name="challenge", text="What evidence?"),
            AgentOutput(agent_name="empathy", text="I hear you."),
            AgentOutput(agent_name="mindfulness", text="Breathe."),
            AgentOutput(agent_name="distortion", text="Feelings aren't facts."),
        ]
        text = assembler.assemble(outputs, user_name="Ravi")
        assert "I hear you." in text  # empathy always opens
        assert "Breathe." in text  # highest-priority specialist wins
        assert "What evidence?" not in text
        assert "Feelings aren't facts." not in text

    def test_grounding_beats_challenging(self, assembler: ResponseAssembler) -> None:
        """When both fire, the one specialist slot goes to the calmer
        agent — never challenge someone instead of grounding them."""
        outputs = [
            AgentOutput(agent_name="distortion", text="Feelings aren't facts."),
            AgentOutput(agent_name="mindfulness", text="Breathe."),
        ]
        text = assembler.assemble(outputs, user_name="Ravi")
        assert "Breathe." in text
        assert "Feelings aren't facts." not in text

    def test_music_text_excluded_from_prose(self, assembler: ResponseAssembler) -> None:
        """Music's text is what the music card renders as its message, so
        including it in the prose showed the same sentence twice."""
        outputs = [
            AgentOutput(agent_name="empathy", text="I hear you."),
            AgentOutput(agent_name="music", text="Try slow ambient."),
        ]
        text = assembler.assemble(outputs, user_name="Ravi")
        assert "I hear you." in text
        assert "Try slow ambient." not in text

    def test_specialist_speaks_when_empathy_absent(
        self, assembler: ResponseAssembler
    ) -> None:
        """Empathy is not guaranteed to have run — the turn must not go
        silent just because the opener is missing."""
        outputs = [AgentOutput(agent_name="reflection", text="What's underneath?")]
        text = assembler.assemble(outputs, user_name="Ravi")
        assert "What's underneath?" in text

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
