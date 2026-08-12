"""Tests for MindLens WebSocket Chat Router."""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.agents.base_agent import AgentOutput
from app.core.connection_manager import ConnectionManager
from app.routers.chat import _CHECKIN_FALLBACK_TEXT, _save_mood_log, _save_pending_checkin
from pymongo.errors import DuplicateKeyError


@pytest.fixture
def mock_db_ws():
    """Mock DB for WebSocket tests."""
    mock = MagicMock()
    mock.users = MagicMock()
    mock.sessions = MagicMock()
    mock.token_blocklist = MagicMock()
    mock.pending_checkins = MagicMock()
    mock.safety_events = MagicMock()
    mock.mood_logs = MagicMock()
    mock.mood_logs.insert_one = AsyncMock()
    return mock


@pytest.fixture
def sample_session_doc() -> dict[str, Any]:
    return {
        "session_id": "sess_abc",
        "user_id": "user_123",
        "title": "Exam stress",
        "started_at": datetime.datetime.now(datetime.UTC),
        "ended_at": None,
        "status": "active",
        "turns": [],
        "eos_timeline": [],
        "agents_used": [],
        "primary_modality": None,
    }


class TestConnectionManager:
    """Unit tests for ConnectionManager without WebSocket."""

    @pytest.fixture
    def manager(self):
        return ConnectionManager(heartbeat_interval=30, max_concurrent_per_user=1)

    @pytest.mark.asyncio

    
    async def test_connect_accepts_websocket(self, manager: ConnectionManager) -> None:

        ws = MagicMock()
        ws.accept = AsyncMock()
        ws.close = AsyncMock()
        ws.send_json = AsyncMock()

        result = await manager.connect(ws, "user_123", "sess_abc")
        assert result is True
        assert manager.is_connected("user_123") is True

        assert manager.get_connection_count() == 1

    @pytest.mark.asyncio
    async def test_disconnect_removes_user(self, manager: ConnectionManager) -> None:
        ws = MagicMock()
        ws.accept = AsyncMock()
        ws.close = AsyncMock()
        ws.send_json = AsyncMock()

        await manager.connect(ws, "user_123", "sess_abc")
        assert manager.is_connected("user_123")

        await manager.disconnect("user_123")
        assert not manager.is_connected("user_123")
        assert manager.get_connection_count() == 0

    @pytest.mark.asyncio
    async def test_single_connection_per_user(self, manager: ConnectionManager) -> None:
        ws1 = MagicMock()
        ws1.accept = AsyncMock()
        ws1.close = AsyncMock()
        ws1.send_json = AsyncMock()

        ws2 = MagicMock()
        ws2.accept = AsyncMock()
        ws2.close = AsyncMock()
        ws2.send_json = AsyncMock()

        await manager.connect(ws1, "user_123", "sess_abc")
        assert manager.is_connected("user_123") is True

        await manager.connect(ws2, "user_123", "sess_def")
        # Old connection should be closed
        ws1.close.assert_awaited_once()
        # New connection should be active
        assert manager.get_user_session_id("user_123") == "sess_def"

    @pytest.mark.asyncio

    async def test_send_to_user_success(self, manager: ConnectionManager) -> None:
        ws = MagicMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()

        await manager.connect(ws, "user_123", "sess_abc")

        result = await manager.send_to_user("user_123", {"type": "hello"})
        assert result is True
        ws.send_json.assert_awaited_with({"type": "hello"})

    @pytest.mark.asyncio
    async def test_send_to_disconnected_user(self, manager: ConnectionManager) -> None:
        result = await manager.send_to_user("user_123", {"type": "hello"})

        assert result is False

    @pytest.mark.asyncio
    async def test_send_thinking_update(self, manager: ConnectionManager) -> None:
        ws = MagicMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()

        await manager.connect(ws, "user_123", "sess_abc")
        result = await manager.send_thinking_update(
            "user_123",
            agents_active=["empathy_agent"],
            eos={"surface_emotion": "anxiety", "distress_level": 0.7},
            memory_recalled=["exam"],
        )
        assert result is True
        call_args = ws.send_json.call_args[0][0]
        assert call_args["type"] == "thinking_update"
        assert call_args["agents_active"] == ["empathy_agent"]
        assert call_args["memory_recalled"] == ["exam"]

    @pytest.mark.asyncio
    async def test_send_response(self, manager: ConnectionManager) -> None:
        ws = MagicMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()

        await manager.connect(ws, "user_123", "sess_abc")
        result = await manager.send_response(
            "user_123",
            text="Hello",
            agents_used=["empathy_agent"],
            eos_snapshot={"surface_emotion": "joy"},
        )
        assert result is True
        call_args = ws.send_json.call_args[0][0]
        assert call_args["type"] == "response"
        assert call_args["text"] == "Hello"
        assert call_args["crisis_flag"] is False

    @pytest.mark.asyncio
    async def test_send_crisis_response(self, manager: ConnectionManager) -> None:
        ws = MagicMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()

        await manager.connect(ws, "user_123", "sess_abc")
        result = await manager.send_crisis_response(
            "user_123",
            text="Please call 1926",
            resources=[{"name": "NIMH", "number": "1926"}],
        )
        assert result is True
        call_args = ws.send_json.call_args[0][0]
        assert call_args["type"] == "crisis_response"
        assert call_args["crisis_flag"] is True
        assert call_args["session_paused"] is True

    @pytest.mark.asyncio

    async def test_get_all_connected_users(self, manager: ConnectionManager) -> None:
        ws1 = MagicMock()
        ws1.accept = AsyncMock()
        ws1.send_json = AsyncMock()

        ws2 = MagicMock()
        ws2.accept = AsyncMock()
        ws2.send_json = AsyncMock()

        await manager.connect(ws1, "user_1", "sess_1")
        await manager.connect(ws2, "user_2", "sess_2")

        users = manager.get_all_connected_users()
        assert sorted(users) == ["user_1", "user_2"]

    @pytest.mark.asyncio
    async def test_get_metadata(self, manager: ConnectionManager) -> None:
        ws = MagicMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()

        await manager.connect(ws, "user_123", "sess_abc")
        meta = manager.get_metadata("user_123")
        assert meta is not None
        assert meta["session_id"] == "sess_abc"
        assert meta["message_count"] == 0


class TestSaveMoodLog:
    """dashboard.py's /mood and /summary read this collection — nothing
    wrote to it until _save_mood_log existed. These tests pin that a normal
    turn logs the real EOS reading, and a crisis turn logs nothing."""

    @pytest.mark.asyncio
    async def test_normal_turn_logs_eos_snapshot(self, mock_db_ws: MagicMock) -> None:
        result = {
            "crisis_flag": False,
            "eos": {
                "surface_emotion": "nervousness",
                "core_emotion": "fear",
                "distress_level": 0.62,
                "valence": "negative",
                "modality": "CBT",
            },
        }

        await _save_mood_log(mock_db_ws, "sess_abc", "user_123", result)

        mock_db_ws.mood_logs.insert_one.assert_awaited_once()
        logged = mock_db_ws.mood_logs.insert_one.call_args[0][0]
        assert logged["user_id"] == "user_123"
        assert logged["session_id"] == "sess_abc"
        assert logged["surface_emotion"] == "nervousness"
        assert logged["distress_level"] == 0.62
        assert "timestamp" in logged

    @pytest.mark.asyncio
    async def test_crisis_turn_is_not_logged(self, mock_db_ws: MagicMock) -> None:
        """Crisis EOS is a hardcoded placeholder (orchestrator.py sets
        distress_level=1.0 unconditionally), not a real inference — logging
        it would fabricate a mood-trend data point."""
        result = {
            "crisis_flag": True,
            "eos": {
                "surface_emotion": "distress",
                "distress_level": 1.0,
            },
        }

        await _save_mood_log(mock_db_ws, "sess_abc", "user_123", result)

        mock_db_ws.mood_logs.insert_one.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_missing_eos_fields_do_not_raise(self, mock_db_ws: MagicMock) -> None:
        result = {"crisis_flag": False, "eos": {}}

        await _save_mood_log(mock_db_ws, "sess_abc", "user_123", result)

        mock_db_ws.mood_logs.insert_one.assert_awaited_once()
        logged = mock_db_ws.mood_logs.insert_one.call_args[0][0]
        assert logged["surface_emotion"] is None


class TestSavePendingCheckin:
    """CheckInAgent (SYSTEM.md §5.12) was registered in the orchestrator but
    never dispatched by _select_agents — only checkin_scheduler (which
    decides *when*) ran. Every proactive check-in used a hardcoded generic
    line instead, which is the exact opener the agent's own prompt forbids.
    These pin that the real agent's text is now what gets stored."""

    @pytest.fixture
    def schedule_result(self) -> dict[str, Any]:
        return {
            "eos": {"surface_emotion": "nervousness", "distress_level": 0.6},
            "agent_outputs": [
                {
                    "agent": "checkin_scheduler",
                    "text": "",
                    "metadata": {
                        "action": "schedule_checkin",
                        "scheduled_at": (
                            datetime.datetime.now(datetime.UTC)
                            + datetime.timedelta(hours=12)
                        ).isoformat(),
                    },
                }
            ],
        }

    @pytest.mark.asyncio
    async def test_uses_generated_checkin_text(
        self, mock_db_ws: MagicMock, schedule_result: dict[str, Any]
    ) -> None:
        mock_db_ws.pending_checkins.update_one = AsyncMock()
        generated = AgentOutput(
            agent_name="checkin",
            text="Hey Amiru — how did that exam go in the end?",
            metadata={},
        )
        with patch(
            "app.routers.chat.CheckInAgent.run",
            new=AsyncMock(return_value=generated),
        ):
            await _save_pending_checkin(
                mock_db_ws, "sess_abc", "user_123", "Amiru", [], schedule_result
            )

        mock_db_ws.pending_checkins.update_one.assert_awaited_once()
        _, kwargs = mock_db_ws.pending_checkins.update_one.call_args
        set_fields = mock_db_ws.pending_checkins.update_one.call_args[0][1]["$set"]
        assert set_fields["text"] == "Hey Amiru — how did that exam go in the end?"
        assert set_fields["text"] != "How are you feeling since our last conversation?"

    @pytest.mark.asyncio
    async def test_falls_back_on_generation_failure(
        self, mock_db_ws: MagicMock, schedule_result: dict[str, Any]
    ) -> None:
        mock_db_ws.pending_checkins.update_one = AsyncMock()
        with patch(
            "app.routers.chat.CheckInAgent.run",
            new=AsyncMock(side_effect=RuntimeError("groq down")),
        ):
            await _save_pending_checkin(
                mock_db_ws, "sess_abc", "user_123", "Amiru", [], schedule_result
            )

        mock_db_ws.pending_checkins.update_one.assert_awaited_once()
        set_fields = mock_db_ws.pending_checkins.update_one.call_args[0][1]["$set"]
        assert set_fields["text"] == _CHECKIN_FALLBACK_TEXT

    @pytest.mark.asyncio
    async def test_no_scheduling_action_does_nothing(self, mock_db_ws: MagicMock) -> None:
        mock_db_ws.pending_checkins.update_one = AsyncMock()
        result = {"eos": {}, "agent_outputs": [{"agent": "empathy", "text": "hi", "metadata": {}}]}

        await _save_pending_checkin(mock_db_ws, "sess_abc", "user_123", "Amiru", [], result)

        mock_db_ws.pending_checkins.update_one.assert_not_awaited()


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
