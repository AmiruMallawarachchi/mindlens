"""MongoDB persistence and read operations for completed sessions."""

from __future__ import annotations

import datetime

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.memory.session_buffer import SessionMemory
from app.memory.session_models import SessionSnapshot, Turn


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
