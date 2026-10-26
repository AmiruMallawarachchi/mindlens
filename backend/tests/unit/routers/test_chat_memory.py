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


class TestSaveExtractedMemory:
    """The write that makes the Memory page's promise true — see
    session_memory_save.py's module docstring."""

    @staticmethod
    def _db():
        db = MagicMock()
        db.user_memory = MagicMock()
        db.user_memory.update_one = AsyncMock()
        return db

    @staticmethod
    def _result(extracted: dict) -> dict:
        return {
            "agent_outputs": [
                {"agent": "session_memory_save", "metadata": {"extracted": extracted}}
            ]
        }

    @pytest.mark.asyncio
    async def test_new_person_written_in_two_steps_no_upsert_on_the_conditional_call(
        self,
    ) -> None:
        """A single upsert=True call with `people.<name>: exists:False` in
        its filter would, once that name exists, match zero documents and
        insert a *second* user_memory document — colliding with the unique
        index on user_id and crashing the turn. Ensuring the document exists
        first, then applying the conditional set with no upsert flag, is
        what makes a name that's already on file a safe no-op instead."""
        from app.routers.chat import _save_extracted_memory

        db = self._db()
        await _save_extracted_memory(
            db, "u1", self._result({"person_relation": "sister", "person_name": "Amaya"})
        )

        assert db.user_memory.update_one.await_count == 2
        ensure_query, ensure_update = db.user_memory.update_one.await_args_list[0].args
        assert ensure_query == {"user_id": "u1"}
        assert db.user_memory.update_one.await_args_list[0].kwargs.get("upsert") is True
        assert ensure_update["$setOnInsert"]["user_id"] == "u1"

        set_query, set_update = db.user_memory.update_one.await_args_list[1].args
        assert set_query == {"user_id": "u1", "people.Amaya": {"$exists": False}}
        assert "upsert" not in db.user_memory.update_one.await_args_list[1].kwargs
        assert set_update["$set"]["people.Amaya"]["role"] == "sister"

    @pytest.mark.asyncio
    async def test_every_person_from_one_turn_is_written(self) -> None:
        """A turn naming two people must write both.

        The writer only ever read `person_name`, so "my boyfriend called
        Hasanka and my mum's name is Rehana" persisted one of them and
        silently dropped the other.
        """
        from app.routers.chat import _save_extracted_memory

        db = self._db()
        await _save_extracted_memory(
            db,
            "u1",
            self._result(
                {
                    "people": [
                        {"name": "Hasanka", "relation": "boyfriend"},
                        {"name": "Rehana", "relation": "mum"},
                    ]
                }
            ),
        )

        # 1 ensure-doc call + one conditional set per person.
        assert db.user_memory.update_one.await_count == 3
        roles = {
            key: value
            for call in db.user_memory.update_one.await_args_list[1:]
            for key, value in call.args[1]["$set"].items()
            if key.startswith("people.")
        }
        assert roles["people.Hasanka"]["role"] == "boyfriend"
        assert roles["people.Rehana"]["role"] == "mum"
        # Each write stays conditional on the name not already being on file.
        for call in db.user_memory.update_one.await_args_list[1:]:
            assert "$exists" in str(call.args[0])
            assert "upsert" not in call.kwargs

    @pytest.mark.asyncio
    async def test_person_name_with_a_dot_is_skipped_not_crashed(self) -> None:
        """A dot is not legal in a Mongo field path. Writing it raises and
        would take every other person in the same turn down with it, so the
        offending name is skipped and the rest still land."""
        from app.routers.chat import _save_extracted_memory

        db = self._db()
        await _save_extracted_memory(
            db,
            "u1",
            self._result(
                {
                    "people": [
                        {"name": "Dr. Perera", "relation": "supervisor"},
                        {"name": "Rehana", "relation": "mum"},
                    ]
                }
            ),
        )

        keys = [
            key
            for call in db.user_memory.update_one.await_args_list[1:]
            for key in call.args[1]["$set"]
            if key.startswith("people.")
        ]
        assert keys == ["people.Rehana"]

    @pytest.mark.asyncio
    async def test_trigger_topic_and_coping_use_add_to_set(self) -> None:
        from app.routers.chat import _save_extracted_memory

        db = self._db()
        await _save_extracted_memory(
            db, "u1", self._result({"trigger_topic": "exams", "effective_coping": "going for a walk"})
        )

        # Call 0 bootstraps the document; call 1 is the actual $addToSet,
        # which is a plain (non-upsert) update once the doc is guaranteed to
        # exist — see _ensure_user_memory_doc.
        assert db.user_memory.update_one.await_count == 2
        assert db.user_memory.update_one.await_args_list[0].kwargs.get("upsert") is True
        query, update = db.user_memory.update_one.await_args_list[1].args
        assert query == {"user_id": "u1"}
        assert update["$addToSet"]["emotional_patterns.trigger_topics"] == "exams"
        assert update["$addToSet"]["emotional_patterns.effective_coping"] == "going for a walk"
        assert "upsert" not in db.user_memory.update_one.await_args_list[1].kwargs

    @pytest.mark.asyncio
    async def test_nothing_extracted_writes_nothing(self) -> None:
        from app.routers.chat import _save_extracted_memory

        db = self._db()
        await _save_extracted_memory(db, "u1", self._result({}))
        db.user_memory.update_one.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_turn_without_the_agent_writes_nothing(self) -> None:
        from app.routers.chat import _save_extracted_memory

        db = self._db()
        await _save_extracted_memory(
            db, "u1", {"agent_outputs": [{"agent": "empathy", "metadata": {}}]}
        )
        db.user_memory.update_one.assert_not_awaited()

class TestEnsureUserMemoryDoc:
    """persistence-review finding: a plain `upsert=True` bootstrap racing a
    concurrent writer for the same user_id (a second backend process, in a
    horizontally-scaled deployment) raises DuplicateKeyError on the unique
    index in db.py — the other writer already did this job, so it must be
    swallowed rather than propagating and crashing the turn."""

    @pytest.mark.asyncio
    async def test_duplicate_key_error_is_swallowed(self) -> None:
        from app.routers.chat import _ensure_user_memory_doc

        db = MagicMock()
        db.user_memory = MagicMock()
        db.user_memory.update_one = AsyncMock(side_effect=DuplicateKeyError("dup"))

        # Must not raise.
        await _ensure_user_memory_doc(db, "u1", datetime.datetime.now(datetime.UTC))
        db.user_memory.update_one.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_a_failed_bootstrap_does_not_block_the_follow_up_write(self) -> None:
        """Exactly the scenario the race produces: our bootstrap loses the
        race and raises, but the concurrent writer already created the
        document, so the caller's next (non-upsert) write still succeeds."""
        from app.routers.chat import _save_introvert_score

        db = MagicMock()
        db.user_memory = MagicMock()
        db.user_memory.update_one = AsyncMock(
            side_effect=[DuplicateKeyError("dup"), None]
        )

        await _save_introvert_score(
            db,
            "u1",
            {
                "agent_outputs": [{
                    "agent": "personality",
                    "metadata": {"score_update": {"introvert_score": 0.4}},
                }]
            },
        )

        assert db.user_memory.update_one.await_count == 2
        second_query, second_update = db.user_memory.update_one.await_args_list[1].args
        assert second_query == {"user_id": "u1"}
        assert second_update["$set"]["preferences.introvert_score"] == 0.4
