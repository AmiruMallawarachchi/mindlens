"""Tests for MindLens Authentication & Authorization Middleware."""

from __future__ import annotations

import time

import pytest
from app.middleware.auth import (
    RateLimitStore,
)

# --- Rate limit tests ---


class TestRateLimitStore:
    @pytest.fixture
    def store(self) -> RateLimitStore:
        return RateLimitStore()

    @pytest.mark.asyncio
    async def test_check_ip_allowed(self, store: RateLimitStore) -> None:
        result = await store.check_ip("127.0.0.1", limit=100)
        assert result is True

    @pytest.mark.asyncio
    async def test_check_ip_exceeded(self, store: RateLimitStore) -> None:
        for _ in range(5):
            await store.check_ip("127.0.0.1", limit=5)
        result = await store.check_ip("127.0.0.1", limit=5)
        assert result is False

    @pytest.mark.asyncio
    async def test_check_ip_window_expires(self, store: RateLimitStore) -> None:
        # Old entries should be cleaned
        for _ in range(5):
            await store.check_ip("127.0.0.1", limit=5, window=0)  # 0-second window
        # All entries are immediately expired
        result = await store.check_ip("127.0.0.1", limit=5, window=0)
        assert result is True

    @pytest.mark.asyncio
    async def test_check_user_allowed(self, store: RateLimitStore) -> None:
        result = await store.check_user("user_123", limit=60)
        assert result is True

    @pytest.mark.asyncio
    async def test_check_user_exceeded(self, store: RateLimitStore) -> None:
        for _ in range(3):
            await store.check_user("user_123", limit=3)
        result = await store.check_user("user_123", limit=3)
        assert result is False

    @pytest.mark.asyncio
    async def test_login_lockout(self, store: RateLimitStore) -> None:
        # Simulate 5 failed attempts
        for _ in range(5):
            await store.record_login_attempt("email@test.com")

        locked = await store.is_locked_out("email@test.com", max_attempts=5)
        assert locked is True

    @pytest.mark.asyncio
    async def test_login_lockout_below_threshold(self, store: RateLimitStore) -> None:
        for _ in range(4):
            await store.record_login_attempt("email@test.com")

        locked = await store.is_locked_out("email@test.com", max_attempts=5)
        assert locked is False

    @pytest.mark.asyncio
    async def test_reset_login_attempts(self, store: RateLimitStore) -> None:
        for _ in range(5):
            await store.record_login_attempt("email@test.com")
        await store.reset_login_attempts("email@test.com")
        locked = await store.is_locked_out("email@test.com", max_attempts=5)
        assert locked is False

    @pytest.mark.asyncio
    async def test_is_locked_out_expires(self, store: RateLimitStore) -> None:
        # Old attempts should expire after 15 min (900s)
        # We simulate by adding an attempt with a very old timestamp
        store._login_attempts["old@test.com"] = [time.time() - 1000]
        locked = await store.is_locked_out("old@test.com", max_attempts=1)
        assert locked is False


