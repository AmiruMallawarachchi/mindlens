"""Unit tests for the Groq client wrapper."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.agents import groq_client as groq_module
from app.agents.groq_client import GroqClient, GroqResponse, get_groq_client


class TestGroqResponse:
    """Validate GroqResponse dataclass."""

    def test_creation(self) -> None:
        r = GroqResponse(text="hello", model_used="llama-3.1-8b")
        assert r.text == "hello"
        assert r.model_used == "llama-3.1-8b"
        assert r.tokens_used == 0


class TestGroqClientStubMode:
    """Validate stub behaviour when no API key."""

    @pytest.fixture
    def stub_client(self) -> GroqClient:
        with patch("app.agents.groq_client.settings") as mock_settings:
            mock_settings.use_openai_stubs = True
            mock_settings.groq_api_key = ""
            mock_settings.is_production = False
            return GroqClient()

    @pytest.mark.asyncio
    async def test_stub_returns_response(self, stub_client: GroqClient) -> None:
        result = await stub_client.chat(
            system_prompt="You are the empathy agent.",
            user_prompt="I feel sad.",
        )
        assert isinstance(result, GroqResponse)
        assert result.model_used == "stub-8B"
        assert result.finish_reason == "stub"
        assert len(result.text) > 0

    @pytest.mark.asyncio
    async def test_stub_detects_empathy(self, stub_client: GroqClient) -> None:
        result = await stub_client.chat(
            system_prompt="You are the empathy agent of MindLens.",
            user_prompt="I feel sad.",
        )
        assert "empathy" in result.text.lower() or "hear" in result.text.lower()

    @pytest.mark.asyncio
    async def test_stub_detects_mindfulness(self, stub_client: GroqClient) -> None:
        result = await stub_client.chat(
            system_prompt="You are the mindfulness agent.",
            user_prompt="I feel anxious.",
        )
        assert "breath" in result.text.lower() or "mindfulness" in result.text.lower()

    @pytest.mark.asyncio
    async def test_stub_respects_max_tokens(self, stub_client: GroqClient) -> None:
        result = await stub_client.chat(
            system_prompt="You are the empathy agent.",
            user_prompt="I feel sad.",
            max_tokens=10,
        )
        # Approximate: 10 tokens * 4 chars ≈ 40 chars max
        assert len(result.text) <= 50

    @pytest.mark.asyncio
    async def test_stub_uses_name(self, stub_client: GroqClient) -> None:
        result = await stub_client.chat(
            system_prompt="User's name: Ravi\nYou are the empathy agent.",
            user_prompt="I feel sad.",
        )
        assert "Ravi" in result.text


class TestGroqClientRealMode:
    """Validate real API path (mocked)."""

    @pytest.fixture
    def real_client(self) -> GroqClient:
        with patch("app.agents.groq_client.settings") as mock_settings, \
             patch("app.agents.groq_client._GROQ_AVAILABLE", True), \
             patch("app.agents.groq_client.AsyncGroq") as mock_async_groq:
            mock_settings.use_openai_stubs = False
            mock_settings.groq_api_key = "gsk_test_key"
            mock_settings.is_production = False
            mock_async_groq.return_value = MagicMock()
            return GroqClient()

    @pytest.mark.asyncio
    async def test_real_mode_initializes_client(self, real_client: GroqClient) -> None:
        assert real_client._client is not None

    @pytest.mark.asyncio
    async def test_chat_with_timeout(self, real_client: GroqClient) -> None:
        mock_client = MagicMock()
        mock_chat = AsyncMock()
        mock_chat.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Hello"), finish_reason="stop")],
            usage=MagicMock(total_tokens=10),
        )
        mock_client.chat.completions.create = mock_chat
        real_client._client = mock_client

        result = await real_client.chat(
            system_prompt="sys",
            user_prompt="user",
            model_tier="8B",
        )
        assert result.text == "Hello"
        assert result.model_used == "llama-3.1-8b-instant"
        assert result.tokens_used == 10

    @pytest.mark.asyncio
    async def test_chat_timeout(self, real_client: GroqClient) -> None:
        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
            result = await real_client.chat(
                system_prompt="sys",
                user_prompt="user",
            )
        assert result.finish_reason == "timeout"
        assert "try again" in result.text.lower()

    @pytest.mark.asyncio
    async def test_chat_api_error(self, real_client: GroqClient) -> None:
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("API down"))
        real_client._client = mock_client

        result = await real_client.chat(
            system_prompt="sys",
            user_prompt="user",
        )
        assert result.finish_reason == "stub"  # Falls back to stub
        assert len(result.text) > 0

    @pytest.mark.asyncio
    async def test_production_api_error_is_unavailable(
        self,
        real_client: GroqClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(groq_module.settings, "app_env", "production")
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("quota"))
        real_client._client = mock_client

        result = await real_client.chat(
            system_prompt="sys",
            user_prompt="user",
        )

        assert result.finish_reason == "provider_unavailable"
        assert result.tokens_used == 0
        assert "temporarily unavailable" in result.text

    @pytest.mark.asyncio
    async def test_70b_tier(self, real_client: GroqClient) -> None:
        mock_client = MagicMock()
        mock_chat = AsyncMock()
        mock_chat.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Deep"), finish_reason="stop")],
            usage=MagicMock(total_tokens=20),
        )
        mock_client.chat.completions.create = mock_chat
        real_client._client = mock_client

        result = await real_client.chat(
            system_prompt="sys",
            user_prompt="user",
            model_tier="70B",
        )
        assert result.model_used == "llama-3.3-70b-versatile"


class TestGroqClientSingleton:
    """Validate module-level singleton."""

    def test_same_instance(self) -> None:
        with patch("app.agents.groq_client.settings") as mock_settings:
            mock_settings.use_openai_stubs = True
            mock_settings.groq_api_key = ""
            mock_settings.is_production = False
            a = get_groq_client()
            b = get_groq_client()
            assert a is b
