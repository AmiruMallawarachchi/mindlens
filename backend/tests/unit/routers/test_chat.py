"""Connection manager and WebSocket authentication protocol tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.core.connection_manager import ConnectionManager


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

class TestWebSocketSubprotocolEcho:
    """RFC 6455 requires echoing an offered subprotocol.

    The frontend always offers `mindlens.jwt.<token>` because a browser
    cannot set headers on a WebSocket. When the cookie branch returned early
    with no selected subprotocol, the server accepted without echoing and
    every browser aborted the handshake with "Sent non-empty
    'Sec-WebSocket-Protocol' header but no response was received".

    It only showed up locally: deployed, frontend and backend are different
    sites so the SameSite=lax cookie never reaches the handshake and the
    subprotocol branch ran. Same-site localhost sends the cookie, so chat was
    broken in development and fine in production.
    """

    @staticmethod
    def _socket(*, cookie=None, auth=None, offered=None):
        from unittest.mock import MagicMock

        ws = MagicMock()
        ws.cookies = {"access_token": cookie} if cookie else {}
        headers = {}
        if auth:
            headers["authorization"] = auth
        if offered:
            headers["sec-websocket-protocol"] = offered
        ws.headers = headers
        return ws

    def test_echoes_subprotocol_even_when_cookie_supplies_the_token(self) -> None:
        from app.routers.chat import _extract_token

        ws = self._socket(cookie="cookie-jwt", offered="mindlens.jwt.header-jwt")
        token, selected = _extract_token(ws)

        # The cookie still wins for identity...
        assert token == "cookie-jwt"
        # ...but the offer must be echoed or the browser drops the handshake.
        assert selected == "mindlens.jwt.header-jwt"

    def test_echoes_subprotocol_when_bearer_header_supplies_the_token(self) -> None:
        from app.routers.chat import _extract_token

        ws = self._socket(auth="Bearer header-jwt", offered="mindlens.jwt.sub-jwt")
        token, selected = _extract_token(ws)
        assert token == "header-jwt"
        assert selected == "mindlens.jwt.sub-jwt"

    def test_subprotocol_alone_still_supplies_the_token(self) -> None:
        from app.routers.chat import _extract_token

        ws = self._socket(offered="mindlens.jwt.only-jwt")
        assert _extract_token(ws) == ("only-jwt", "mindlens.jwt.only-jwt")

    def test_nothing_offered_echoes_nothing(self) -> None:
        """A non-browser client that offers no subprotocol must not be sent
        one back — echoing an unoffered protocol is equally invalid."""
        from app.routers.chat import _extract_token

        ws = self._socket(cookie="cookie-jwt")
        assert _extract_token(ws) == ("cookie-jwt", None)

    def test_ignores_unrelated_offered_protocols(self) -> None:
        from app.routers.chat import _extract_token

        ws = self._socket(cookie="cookie-jwt", offered="graphql-ws, someother")
        assert _extract_token(ws) == ("cookie-jwt", None)
