"""Focused tests for WebSocket chat service behavior."""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.agents.base_agent import AgentOutput
from app.core.connection_manager import ConnectionManager
from app.routers.chat import (
    _CHECKIN_FALLBACK_TEXT,
    _ensure_user_memory_doc,
    _save_extracted_memory,
    _save_introvert_score,
    _save_mood_log,
    _save_pending_checkin,
)
from pymongo.errors import DuplicateKeyError
from .chat_test_fixtures import mock_db_ws, sample_session_doc


class TestSaveIntrovertScore:
    """T2 — the write that closes the personality loop."""

    @staticmethod
    def _db():
        db = MagicMock()
        db.user_memory = MagicMock()
        db.user_memory.update_one = AsyncMock()
        return db

    @staticmethod
    def _result(metadata: dict) -> dict:
        return {"agent_outputs": [{"agent": "personality", "metadata": metadata}]}

    @pytest.mark.asyncio
    async def test_score_is_written_with_a_dotted_path(self) -> None:
        """A whole-subdocument $set would wipe the user's typed settings."""
        from app.routers.chat import _save_introvert_score

        db = self._db()
        await _save_introvert_score(
            db, "u1", self._result({"score_update": {"introvert_score": 0.31}})
        )

        # Call 0 bootstraps the document (_ensure_user_memory_doc); call 1 is
        # the actual score write, which is why it's asserted by position.
        assert db.user_memory.update_one.await_count == 2
        query, update = db.user_memory.update_one.await_args_list[1].args[:2]
        assert query == {"user_id": "u1"}
        assert update["$set"]["preferences.introvert_score"] == 0.31
        # Nothing may overwrite `preferences` wholesale.
        assert "preferences" not in update["$set"]

    @pytest.mark.asyncio
    async def test_write_is_scoped_to_the_user(self) -> None:
        from app.routers.chat import _save_introvert_score

        db = self._db()
        await _save_introvert_score(
            db, "u42", self._result({"score_update": {"introvert_score": 0.6}})
        )
        assert db.user_memory.update_one.await_args.args[0]["user_id"] == "u42"

    @pytest.mark.asyncio
    async def test_skipped_turn_writes_nothing(self) -> None:
        from app.routers.chat import _save_introvert_score

        db = self._db()
        await _save_introvert_score(
            db, "u1", self._result({"skipped": True, "introvert_score": 0.5})
        )
        db.user_memory.update_one.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_turn_without_the_agent_writes_nothing(self) -> None:
        from app.routers.chat import _save_introvert_score

        db = self._db()
        await _save_introvert_score(
            db, "u1", {"agent_outputs": [{"agent": "empathy", "metadata": {}}]}
        )
        db.user_memory.update_one.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_malformed_score_writes_nothing(self) -> None:
        from app.routers.chat import _save_introvert_score

        db = self._db()
        await _save_introvert_score(
            db, "u1", self._result({"score_update": {"introvert_score": "high"}})
        )
        db.user_memory.update_one.assert_not_awaited()

class TestSaveIntrovertScoreUpsert:
    """Regression — nothing gates chat behind onboarding completion, so the
    user_memory document is not guaranteed to exist when a turn runs."""

    @pytest.mark.asyncio
    async def test_write_upserts_so_a_missing_document_is_not_silent_loss(self) -> None:
        from app.routers.chat import _save_introvert_score

        db = MagicMock()
        db.user_memory = MagicMock()
        db.user_memory.update_one = AsyncMock()

        await _save_introvert_score(
            db,
            "u1",
            {"agent_outputs": [{
                "agent": "personality",
                "metadata": {"score_update": {"introvert_score": 0.4}},
            }]},
        )

        # The bootstrap call (call 0) is the one that upserts, so a missing
        # document doesn't discard the inference — see _ensure_user_memory_doc.
        first_kwargs = db.user_memory.update_one.await_args_list[0].kwargs
        assert first_kwargs.get("upsert") is True
        first_update = db.user_memory.update_one.await_args_list[0].args[1]
        assert first_update["$setOnInsert"]["user_id"] == "u1"
