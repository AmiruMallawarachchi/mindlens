"""End-to-end wiring tests for the chat WebSocket path.

The V2 graph produces a reply; these two seams are where the "nothing ever
wrote to user_memory / pending_checkins" bug lived, so they are tested at the
call site rather than only through the services.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.routers.chat_services.flow import run_chat_message_loop
from fastapi import WebSocketDisconnect


class TestMemoryExtractionWiring:
    @pytest.mark.asyncio
    async def test_one_turn_writes_the_person_and_topic_to_memory(self) -> None:
        websocket = MagicMock()
        websocket.receive_json = AsyncMock(
            side_effect=[
                {
                    "type": "message",
                    "text": "My sister Amaya called and my exam went badly.",
                },
                TimeoutError(),
            ]
        )
        websocket.close = AsyncMock()

        db = MagicMock()
        db.sessions.find_one = AsyncMock(return_value=None)
        db.sessions.update_one = AsyncMock()
        db.mood_logs.insert_one = AsyncMock()
        db.user_memory.find_one = AsyncMock(
            return_value={"preferences": {"memory_depth": "everything"}}
        )
        db.user_memory.update_one = AsyncMock()
        db.safety_events.insert_one = AsyncMock()

        orchestrator = MagicMock()
        orchestrator.run_full_pipeline = AsyncMock(
            return_value={
                "assembled_text": "That sounds like a heavy day.",
                "agents": ["empathy"],
                "crisis_flag": False,
                "eos": {
                    "surface_emotion": "sadness",
                    "distress_level": 0.8,
                    "valence": "negative",
                },
            }
        )

        rate_limit = MagicMock()
        rate_limit.check_user = AsyncMock(return_value=True)

        with (
            patch(
                "app.routers.chat_services.flow.get_rate_limit_store",
                return_value=rate_limit,
            ),
            patch(
                "app.routers.chat_services.flow.stream_pipeline_result",
                new=AsyncMock(),
            ),
        ):
            await run_chat_message_loop(
                websocket=websocket,
                db=db,
                session_id="sess_abc",
                user_id="user_123",
                user_name="Amiru",
                conn_manager=MagicMock(),
                orchestrator=orchestrator,
            )

        writes = [
            call.args[1]
            for call in db.user_memory.update_one.await_args_list
            if len(call.args) > 1
        ]
        assert any("people.Amaya" in str(write) for write in writes)
        assert any(
            write.get("$addToSet", {}).get("emotional_patterns.trigger_topics") == "exams"
            for write in writes
        )

    @pytest.mark.asyncio
    async def test_crisis_turn_does_not_write_memory(self) -> None:
        websocket = MagicMock()
        websocket.receive_json = AsyncMock(
            side_effect=[
                {"type": "message", "text": "My sister Amaya says I should end it."},
                TimeoutError(),
            ]
        )
        websocket.close = AsyncMock()

        db = MagicMock()
        db.sessions.find_one = AsyncMock(return_value=None)
        db.sessions.update_one = AsyncMock()
        db.mood_logs.insert_one = AsyncMock()
        db.user_memory.find_one = AsyncMock(return_value={"preferences": {}})
        db.user_memory.update_one = AsyncMock()
        db.safety_events.insert_one = AsyncMock()

        orchestrator = MagicMock()
        orchestrator.run_full_pipeline = AsyncMock(
            return_value={
                "assembled_text": "Please reach out to 1926.",
                "agents": ["crisis"],
                "crisis_flag": True,
                "eos": {"surface_emotion": "fear", "distress_level": 1.0},
            }
        )
        rate_limit = MagicMock()
        rate_limit.check_user = AsyncMock(return_value=True)

        with (
            patch(
                "app.routers.chat_services.flow.get_rate_limit_store",
                return_value=rate_limit,
            ),
            patch(
                "app.routers.chat_services.flow.stream_pipeline_result",
                new=AsyncMock(),
            ),
        ):
            await run_chat_message_loop(
                websocket=websocket,
                db=db,
                session_id="sess_abc",
                user_id="user_123",
                user_name="Amiru",
                conn_manager=MagicMock(),
                orchestrator=orchestrator,
            )

        db.user_memory.update_one.assert_not_awaited()


class TestCheckinSchedulingWiring:
    @pytest.mark.asyncio
    async def test_disconnect_schedules_a_checkin_for_the_finished_session(self) -> None:
        from app.routers.chat import websocket_chat

        websocket = MagicMock()
        websocket.headers = {}
        websocket.cookies = {"access_token": "jwt"}
        websocket.close = AsyncMock()

        db = MagicMock()
        db.sessions.find_one = AsyncMock(
            return_value={"session_id": "sess_abc", "user_id": "user_123"}
        )
        db.sessions.update_one = AsyncMock()
        db.users.find_one = AsyncMock(return_value={"nickname": "Amiru"})

        connection_manager = MagicMock()
        connection_manager.connect = AsyncMock(return_value=True)
        connection_manager.disconnect = AsyncMock()

        schedule = AsyncMock()

        with (
            patch(
                "app.routers.chat.verify_access_token",
                return_value=MagicMock(id="user_123"),
            ),
            patch("app.routers.chat.get_connection_manager", return_value=connection_manager),
            patch("app.routers.chat.get_hosted_orchestrator", return_value=MagicMock()),
            patch("app.routers.chat.send_pending_checkin", new=AsyncMock()),
            patch(
                "app.routers.chat.run_chat_message_loop",
                new=AsyncMock(side_effect=WebSocketDisconnect()),
            ),
            patch("app.routers.chat.schedule_checkin", new=schedule),
        ):
            await websocket_chat(websocket, "sess_abc", db)

        schedule.assert_awaited_once_with(
            db,
            session_id="sess_abc",
            user_id="user_123",
            user_name="Amiru",
        )
