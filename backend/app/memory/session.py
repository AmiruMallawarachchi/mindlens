"""
Session Memory Management

Three-tier memory system:
1. Turn Buffer (10-turn, in-memory) — current conversation
2. Session Memory (MongoDB) — full transcript + summary + EOS timeline
3. Longitudinal Memory (MongoDB) — mood trends + people graph + historical patterns

This file implements tier 1 & 2.
"""

import datetime

import pydantic
from motor.motor_asyncio import AsyncIOMotorDatabase

# --- Schemas ---


class Turn(pydantic.BaseModel):
    """Single conversational turn."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime.datetime
    emotion: str | None = None  # user emotion (if detected)
    distress: float | None = None  # user distress level (0-1)


class SessionSnapshot(pydantic.BaseModel):
    """EOS state at a specific point in session."""

    turn_number: int
    timestamp: datetime.datetime
    surface_emotion: str
    core_emotion: str
    distress_level: float
    trust_level: float
    alliance_score: float
    modality: str  # "CBT", "Mindfulness", etc.


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


class SessionPersistence:
    """
    MongoDB persistence layer for sessions.

    Handles:
    - Saving session + full transcript
    - Loading session history
    - Updating session summary after completion
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def save_session(
        self,
        session_id: str,
        user_id: str,
        memory: SessionMemory,
        summary: str,
        modality: str,
    ) -> None:
        """
        Save completed session to MongoDB.

        Args:
            session_id: Unique session identifier
            user_id: User who participated
            memory: SessionMemory object with all turns
            summary: AI-generated session summary
            modality: Therapy modality used (CBT, Mindfulness, etc.)
        """
        session_doc = {
            "_id": session_id,
            "user_id": user_id,
            "started_at": memory.created_at,
            "ended_at": datetime.datetime.utcnow(),
            "summary": summary,
            "modality": modality,
            "turn_count": len(memory.turns),
            "transcript": [
                {
                    "role": turn.role,
                    "content": turn.content,
                    "timestamp": turn.timestamp,
                    "emotion": turn.emotion,
                    "distress": turn.distress,
                }
                for turn in memory.turns
            ],
            "eos_timeline": [
                {
                    "turn_number": snap.turn_number,
                    "timestamp": snap.timestamp,
                    "surface_emotion": snap.surface_emotion,
                    "core_emotion": snap.core_emotion,
                    "distress_level": snap.distress_level,
                    "trust_level": snap.trust_level,
                    "alliance_score": snap.alliance_score,
                    "modality": snap.modality,
                }
                for snap in memory.eos_timeline
            ],
        }

        await self.db.sessions.insert_one(session_doc)

    async def load_session(self, session_id: str) -> dict | None:
        """
        Load a completed session from MongoDB.

        Args:
            session_id: Session to retrieve

        Returns:
            Session document or None if not found
        """
        return await self.db.sessions.find_one({"_id": session_id})

    async def get_user_sessions(self, user_id: str, limit: int = 10) -> list[dict]:
        """
        Get recent sessions for a user.

        Args:
            user_id: User to fetch sessions for
            limit: Max sessions to return

        Returns:
            List of session documents (without full transcripts)
        """
        cursor = self.db.sessions.find({"user_id": user_id}).sort(
            "ended_at", -1
        ).limit(limit)

        sessions = []
        async for session in cursor:
            # Return summary view (no full transcript)
            sessions.append({
                "_id": session["_id"],
                "started_at": session["started_at"],
                "ended_at": session["ended_at"],
                "summary": session["summary"],
                "modality": session["modality"],
                "turn_count": session["turn_count"],
            })
        return sessions

    async def get_session_transcript(self, session_id: str) -> list[Turn] | None:
        """
        Load full transcript for a session.

        Args:
            session_id: Session to fetch

        Returns:
            List of Turn objects or None
        """
        session = await self.db.sessions.find_one({"_id": session_id})
        if not session:
            return None

        return [Turn(**turn_data) for turn_data in session.get("transcript", [])]

    async def get_session_eos_timeline(
        self, session_id: str
    ) -> list[SessionSnapshot] | None:
        """
        Load EOS state changes for a session.

        Args:
            session_id: Session to fetch

        Returns:
            List of SessionSnapshot objects or None
        """
        session = await self.db.sessions.find_one({"_id": session_id})
        if not session:
            return None

        return [
            SessionSnapshot(**snap_data)
            for snap_data in session.get("eos_timeline", [])
        ]

    async def get_user_session_stats(self, user_id: str) -> dict:
        """
        Get aggregate statistics about a user's sessions.

        Args:
            user_id: User to analyze

        Returns:
            Dict with session count, avg turns, modalities used, etc.
        """
        sessions = await self.db.sessions.find({"user_id": user_id}).to_list(None)

        if not sessions:
            return {
                "total_sessions": 0,
                "total_turns": 0,
                "avg_turns_per_session": 0,
                "modalities_used": [],
                "first_session": None,
                "last_session": None,
            }

        total_turns = sum(s["turn_count"] for s in sessions)
        modalities = {}
        for session in sessions:
            modality = session.get("modality", "Unknown")
            modalities[modality] = modalities.get(modality, 0) + 1

        return {
            "total_sessions": len(sessions),
            "total_turns": total_turns,
            "avg_turns_per_session": (
                total_turns / len(sessions) if sessions else 0
            ),
            "modalities_used": modalities,
            "first_session": min(s["started_at"] for s in sessions),
            "last_session": max(s["ended_at"] for s in sessions),
        }
