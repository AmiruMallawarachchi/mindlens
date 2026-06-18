"""
Unit tests for session memory management
"""

import datetime

from backend.app.memory.session import SessionMemory, SessionSnapshot, Turn


class TestSessionMemory:
    """Test in-memory session buffer."""

    def test_init(self):
        """SessionMemory should initialize correctly."""
        memory = SessionMemory("sess_123", "user_456")
        assert memory.session_id == "sess_123"
        assert memory.user_id == "user_456"
        assert len(memory.turns) == 0
        assert len(memory.eos_timeline) == 0

    def test_add_turn(self):
        """Adding turns should update buffer."""
        memory = SessionMemory("sess_123", "user_456")

        memory.add_turn("user", "Hello")
        assert len(memory.turns) == 1
        assert memory.turns[0].role == "user"
        assert memory.turns[0].content == "Hello"

    def test_add_multiple_turns(self):
        """Multiple turns should be stored in order."""
        memory = SessionMemory("sess_123", "user_456")

        memory.add_turn("user", "Hi there")
        memory.add_turn("assistant", "Hello! How can I help?")
        memory.add_turn("user", "I'm feeling anxious")

        assert len(memory.turns) == 3
        assert memory.turns[0].content == "Hi there"
        assert memory.turns[1].content == "Hello! How can I help?"
        assert memory.turns[2].content == "I'm feeling anxious"

    def test_buffer_max_turns_limit(self):
        """Buffer should keep only last N turns."""
        memory = SessionMemory("sess_123", "user_456")
        max_turns = memory.max_turns

        # Add more than max turns
        for i in range(max_turns + 5):
            memory.add_turn("user", f"Message {i}")

        # Should only keep last N
        assert len(memory.turns) == max_turns
        # First message should be dropped
        assert memory.turns[0].content == "Message 5"
        # Last message should be recent
        assert memory.turns[-1].content == f"Message {max_turns + 4}"

    def test_turn_count(self):
        """turn_count should reflect actual turns."""
        memory = SessionMemory("sess_123", "user_456")

        assert memory.turn_count() == 0

        memory.add_turn("user", "Hello")
        assert memory.turn_count() == 1

        memory.add_turn("assistant", "Hi")
        assert memory.turn_count() == 2

    def test_get_last_n_turns(self):
        """get_last_n_turns should return recent turns."""
        memory = SessionMemory("sess_123", "user_456")

        for i in range(5):
            memory.add_turn("user", f"Message {i}")

        last_3 = memory.get_last_n_turns(3)
        assert len(last_3) == 3
        assert last_3[0].content == "Message 2"
        assert last_3[-1].content == "Message 4"

    def test_get_last_n_turns_fewer_than_available(self):
        """get_last_n_turns with N > buffer should return all."""
        memory = SessionMemory("sess_123", "user_456")

        memory.add_turn("user", "Message 1")
        memory.add_turn("user", "Message 2")

        last_5 = memory.get_last_n_turns(5)
        assert len(last_5) == 2

    def test_add_emotion_data(self):
        """Turns should store emotion data if provided."""
        memory = SessionMemory("sess_123", "user_456")

        memory.add_turn(
            "user",
            "I'm really stressed",
            emotion="anxiety",
            distress=0.8,
        )

        assert memory.turns[0].emotion == "anxiety"
        assert memory.turns[0].distress == 0.8

    def test_add_eos_snapshot(self):
        """EOS snapshots should be recorded."""
        memory = SessionMemory("sess_123", "user_456")

        snapshot = SessionSnapshot(
            turn_number=1,
            timestamp=datetime.datetime.utcnow(),
            surface_emotion="anxious",
            core_emotion="fear",
            distress_level=0.7,
            trust_level=0.5,
            alliance_score=0.6,
            modality="CBT",
        )

        memory.add_eos_snapshot(snapshot)
        assert len(memory.eos_timeline) == 1
        assert memory.eos_timeline[0].surface_emotion == "anxious"

    def test_get_summary_context(self):
        """get_summary_context should provide session overview."""
        memory = SessionMemory("sess_123", "user_456")

        memory.add_turn("user", "Hello, I'm feeling down", emotion="sadness")
        memory.add_turn("assistant", "I'm here to help.")
        memory.add_turn("user", "Things aren't working out", emotion="sadness")

        context = memory.get_summary_context()

        assert context["session_id"] == "sess_123"
        assert context["user_id"] == "user_456"
        assert context["turn_count"] == 3
        assert context["user_turn_count"] == 2
        assert context["assistant_turn_count"] == 1
        assert "sadness" in context["emotions_detected"]
        assert context["first_message"] == "Hello, I'm feeling down"
        assert context["final_message"] == "Things aren't working out"

    def test_turn_timestamps(self):
        """Each turn should have a timestamp."""
        memory = SessionMemory("sess_123", "user_456")

        before = datetime.datetime.utcnow()
        memory.add_turn("user", "Hello")
        after = datetime.datetime.utcnow()

        turn = memory.turns[0]
        assert before <= turn.timestamp <= after

    def test_consecutive_turns_different_timestamps(self):
        """Consecutive turns should have slightly different timestamps."""
        memory = SessionMemory("sess_123", "user_456")

        memory.add_turn("user", "First")
        memory.add_turn("assistant", "Second")

        assert memory.turns[0].timestamp != memory.turns[1].timestamp


class TestTurnSchema:
    """Test Turn Pydantic model."""

    def test_turn_creation(self):
        """Turn should be created with required fields."""
        turn = Turn(
            role="user",
            content="Hello world",
            timestamp=datetime.datetime.utcnow(),
        )
        assert turn.role == "user"
        assert turn.content == "Hello world"

    def test_turn_optional_fields(self):
        """Emotion and distress should be optional."""
        turn = Turn(
            role="assistant",
            content="Response",
            timestamp=datetime.datetime.utcnow(),
        )
        assert turn.emotion is None
        assert turn.distress is None

    def test_turn_with_emotion(self):
        """Turn can include emotion data."""
        turn = Turn(
            role="user",
            content="I'm stressed",
            timestamp=datetime.datetime.utcnow(),
            emotion="stress",
            distress=0.75,
        )
        assert turn.emotion == "stress"
        assert turn.distress == 0.75


class TestSessionSnapshot:
    """Test SessionSnapshot model."""

    def test_snapshot_creation(self):
        """SessionSnapshot should capture EOS state."""
        now = datetime.datetime.utcnow()
        snapshot = SessionSnapshot(
            turn_number=1,
            timestamp=now,
            surface_emotion="happy",
            core_emotion="contentment",
            distress_level=0.2,
            trust_level=0.8,
            alliance_score=0.9,
            modality="Mindfulness",
        )
        assert snapshot.turn_number == 1
        assert snapshot.surface_emotion == "happy"
        assert snapshot.distress_level == 0.2
        assert snapshot.modality == "Mindfulness"
