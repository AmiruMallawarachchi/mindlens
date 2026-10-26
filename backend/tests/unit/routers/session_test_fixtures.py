"""Fixtures shared by session router tests."""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

def _make_async_cursor(docs: list[dict]) -> Any:
    """Return a mock MongoDB cursor that works with async for."""

    async def _async_generator():
        for doc in docs:
            yield doc

    class _Cursor:
        def __init__(self, docs: list[dict]) -> None:
            self._docs = docs

        def skip(self, n: int) -> _Cursor:
            return self

        def limit(self, n: int) -> _Cursor:
            return self

        def sort(self, *args, **kwargs) -> _Cursor:
            return self

        def __aiter__(self) -> Any:
            return _async_generator().__aiter__()

    return _Cursor(docs)


@pytest.fixture
async def session_client(mock_db: MagicMock):
    """FastAPI test client with mocked DB for session tests."""
    from app.main import app
    from httpx import ASGITransport, AsyncClient

    async def override_get_db():
        return mock_db

    app.dependency_overrides = {}
    from app.db import get_db
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def sample_user_doc() -> dict[str, Any]:
    return {
        "_id": "user_123",
        "email": "test@example.com",
        "name": "Amiru",
        "nickname": "Ami",
        "age": 22,
        "age_group": "adult",
        "role": "user",
        "is_active": True,
        "onboarding_complete": False,
        "created_at": datetime.datetime.now(datetime.UTC),
    }


@pytest.fixture
def sample_session_doc() -> dict[str, Any]:
    return {
        "session_id": "sess_abc",
        "user_id": "user_123",
        "title": "Exam stress",
        "context": None,
        "started_at": datetime.datetime.now(datetime.UTC),
        "ended_at": None,
        "status": "active",
        "turns": [],
        "eos_timeline": [],
        "session_summary": "",
        "key_facts": [],
        "agents_used": [],
        "primary_modality": None,
        "check_in_scheduled": False,
        "updated_at": datetime.datetime.now(datetime.UTC),
    }


