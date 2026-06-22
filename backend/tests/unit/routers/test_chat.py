"""Tests for MindLens WebSocket Chat Router."""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.core.connection_manager import ConnectionManager
from app.middleware.auth import create_token_pair


@pytest.fixture
def mock_db_ws():
    """Mock DB for WebSocket tests."""
    mock = MagicMock()
    mock.users = MagicMock()
    mock.sessions = MagicMock()
    mock.token_blocklist = MagicMock()
    mock.pending_checkins = MagicMock()
    mock.safety_events = MagicMock()
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
