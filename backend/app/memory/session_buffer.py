"""In-memory bounded turn buffer for an active conversation."""

from __future__ import annotations

import datetime

from app.memory.session_models import SessionSnapshot, Turn


class SessionMemory:
    """
    In-memory 10-turn buffer for current session.

    Keeps the last 10 turns (user + assistant messages) in memory.
    When session ends, all turns are saved to MongoDB with summary and EOS timeline.
    """

    def __init__(self, session_id: str, user_id: str):
        self.session_id = session_id
        self.user_id = user_id
        self.created_at = datetime.datetime.utcnow()
        self.turns: list[Turn] = []
        self.eos_timeline: list[SessionSnapshot] = []
        self.max_turns = 10

    def add_turn(
        self,
        role: str,
        content: str,
        emotion: str | None = None,
        distress: float | None = None,
    ) -> None:
        """
        Add a turn to the buffer.

        If buffer exceeds max_turns, oldest turn is dropped.
        """
        timestamp = datetime.datetime.utcnow()
        if self.turns and timestamp <= self.turns[-1].timestamp:
            timestamp = self.turns[-1].timestamp + datetime.timedelta(microseconds=1)
        turn = Turn(
            role=role,
            content=content,
            timestamp=timestamp,
            emotion=emotion,
            distress=distress,
        )
        self.turns.append(turn)

        # Keep only last N turns
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns :]

    def add_eos_snapshot(self, snapshot: SessionSnapshot) -> None:
        """Record EOS state at a point in time."""
        self.eos_timeline.append(snapshot)

    def get_last_n_turns(self, n: int = 3) -> list[Turn]:
        """Get last N turns for context window."""
        return self.turns[-n:] if len(self.turns) >= n else self.turns

    def get_all_turns(self) -> list[Turn]:
        """Get all turns in current buffer."""
        return self.turns

    def turn_count(self) -> int:
        """Total turns in this session so far."""
        return len(self.turns)

    def get_summary_context(self) -> dict:
        """
        Get context for session summary generation.

        Used by backend to create concise session summaries.
        """
        if not self.turns:
            return {}

        user_turns = [t for t in self.turns if t.role == "user"]
        assistant_turns = [t for t in self.turns if t.role == "assistant"]

        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "turn_count": len(self.turns),
            "user_turn_count": len(user_turns),
            "assistant_turn_count": len(assistant_turns),
            "first_message": user_turns[0].content if user_turns else None,
            "final_message": user_turns[-1].content if user_turns else None,
            "emotions_detected": list({t.emotion for t in user_turns if t.emotion}),
            "distress_values": [t.distress for t in user_turns if t.distress],
            "eos_timeline_length": len(self.eos_timeline),
            "created_at": self.created_at,
            "last_activity": self.turns[-1].timestamp if self.turns else None,
        }


