"""Tests for MindLens Connection Manager."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.core.connection_manager import ConnectionManager, get_connection_manager


class TestConnectionManagerBasics:
    """Unit tests for ConnectionManager."""

    @pytest.fixture
    async def manager(self) -> ConnectionManager:
        manager = ConnectionManager(heartbeat_interval=30, max_concurrent_per_user=1)
        yield manager
        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_connect_accepts_websocket(self, manager: ConnectionManager) -> None:
        ws = MagicMock()
        ws.accept = AsyncMock()
        ws.close = AsyncMock()
        ws.send_json = AsyncMock()

        result = await manager.connect(ws, "user_123", "sess_abc")
        assert result is True
        assert manager.is_connected("user_123")
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
    async def test_reconnect_closes_old_connection(self, manager: ConnectionManager) -> None:
        ws1 = MagicMock()
        ws1.accept = AsyncMock()
        ws1.close = AsyncMock()
        ws1.send_json = AsyncMock()

        ws2 = MagicMock()
        ws2.accept = AsyncMock()
        ws2.close = AsyncMock()
        ws2.send_json = AsyncMock()

        await manager.connect(ws1, "user_123", "sess_abc")
        await manager.connect(ws2, "user_123", "sess_def")

        ws1.close.assert_awaited_once()
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
    async def test_send_to_user_failure(self, manager: ConnectionManager) -> None:
        ws = MagicMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock(side_effect=RuntimeError("Connection broken"))

        await manager.connect(ws, "user_123", "sess_abc")
        result = await manager.send_to_user("user_123", {"type": "hello"})
        assert result is False

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
        await manager.send_thinking_update(
            "user_123",
            agents_active=["safety_gate", "empathy_agent"],
            eos={"surface_emotion": "anxiety", "distress_level": 0.7},
            memory_recalled=["exam", "Ravi"],
        )

        call_args = ws.send_json.call_args[0][0]
        assert call_args["type"] == "thinking_update"
        assert call_args["agents_active"] == ["safety_gate", "empathy_agent"]
        assert call_args["memory_recalled"] == ["exam", "Ravi"]
        assert call_args["eos"]["distress_level"] == 0.7

    @pytest.mark.asyncio
    async def test_send_response(self, manager: ConnectionManager) -> None:
        ws = MagicMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()

        await manager.connect(ws, "user_123", "sess_abc")
        await manager.send_response(
            "user_123",
            text="I hear you.",
            agents_used=["empathy_agent"],
            eos_snapshot={"surface_emotion": "sadness"},
            music={"tracks": ["Weightless"]},
        )

        call_args = ws.send_json.call_args[0][0]
        assert call_args["type"] == "response"
        assert call_args["text"] == "I hear you."
        assert call_args["music"]["tracks"] == ["Weightless"]
        assert call_args["crisis_flag"] is False

    @pytest.mark.asyncio
    async def test_send_crisis_response(self, manager: ConnectionManager) -> None:
        ws = MagicMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()

        await manager.connect(ws, "user_123", "sess_abc")
        await manager.send_crisis_response(
            "user_123",
            text="Please reach out to NIMH.",
            resources=[{"name": "NIMH Sri Lanka", "number": "1926"}],
        )

        call_args = ws.send_json.call_args[0][0]
        assert call_args["type"] == "crisis_response"
        assert call_args["crisis_flag"] is True
        assert call_args["session_paused"] is True
        assert call_args["resources"][0]["number"] == "1926"

    @pytest.mark.asyncio
    async def test_send_chunk(self, manager: ConnectionManager) -> None:
        ws = MagicMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()

        await manager.connect(ws, "user_123", "sess_abc")
        await manager.send_chunk("user_123", "Hello", 0)
        await manager.send_chunk("user_123", " world", 1)

        assert ws.send_json.call_count == 2
        first = ws.send_json.call_args_list[0][0][0]
        second = ws.send_json.call_args_list[1][0][0]
        assert first["type"] == "stream_chunk"
        assert first["chunk"] == "Hello"
        assert first["index"] == 0
        assert second["chunk"] == " world"
        assert second["index"] == 1

    @pytest.mark.asyncio
    async def test_send_stream_end(self, manager: ConnectionManager) -> None:
        ws = MagicMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()

        await manager.connect(ws, "user_123", "sess_abc")
        await manager.send_stream_end("user_123")

        call_args = ws.send_json.call_args[0][0]
        assert call_args["type"] == "stream_end"

    @pytest.mark.asyncio
    async def test_send_checkin(self, manager: ConnectionManager) -> None:
        ws = MagicMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()

        await manager.connect(ws, "user_123", "sess_abc")
        await manager.send_checkin("user_123", "How are you doing?", "sess_xyz")

        call_args = ws.send_json.call_args[0][0]
        assert call_args["type"] == "checkin"
        assert call_args["text"] == "How are you doing?"
        assert call_args["from_session"] == "sess_xyz"

    @pytest.mark.asyncio
    async def test_metadata_tracking(self, manager: ConnectionManager) -> None:
        ws = MagicMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()

        await manager.connect(ws, "user_123", "sess_abc")
        meta = manager.get_metadata("user_123")
        assert meta is not None
        assert meta["session_id"] == "sess_abc"
        assert meta["message_count"] == 0

        await manager.send_to_user("user_123", {"type": "test"})
        meta = manager.get_metadata("user_123")
        assert meta["message_count"] == 1

    def test_get_connection_count_empty(self, manager: ConnectionManager) -> None:
        assert manager.get_connection_count() == 0

    def test_get_all_connected_users_empty(self, manager: ConnectionManager) -> None:
        assert manager.get_all_connected_users() == []

    def test_get_metadata_disconnected(self, manager: ConnectionManager) -> None:
        assert manager.get_metadata("nonexistent") is None


class TestSingleton:
    """Tests for the singleton getter."""

    def test_get_connection_manager_returns_singleton(self) -> None:
        m1 = get_connection_manager()
        m2 = get_connection_manager()
        assert m1 is m2

    def test_get_connection_manager_with_custom_params(self) -> None:
        m = get_connection_manager(heartbeat_interval=60, max_concurrent_per_user=2)
        assert m._heartbeat_interval == 60
        assert m._max_concurrent == 2
