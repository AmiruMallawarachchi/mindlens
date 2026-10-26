"""Unit tests for the account router — device sessions, export, deletion.

No test file existed for this router before this. That is the worst place
in the codebase to have zero coverage: this is the surface that makes the
privacy promise real (see the router's own module docstring) — sign a
device out, download everything held, hard-delete an account. A silent
regression here is a silent broken promise.
"""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.db import get_db
from app.middleware.auth import create_token_pair
from app.routers.account import USER_DATA_COLLECTIONS, device_label
from httpx import ASGITransport, AsyncClient


def _cursor(docs: list[dict]) -> Any:
    """Mock cursor supporting async for and the chained .sort()/.to_list()
    calls account.py makes — same shape as test_session.py's helper, kept
    local since the two files don't share a fixture module."""

    async def _gen():
        for doc in docs:
            yield doc

    class _Cursor:
        def __init__(self, items: list[dict]) -> None:
            self._items = items

        def sort(self, *a, **kw) -> _Cursor:
            return self

        async def to_list(self, length: int = 0) -> list[dict]:
            return self._items

        def __aiter__(self):
            return _gen().__aiter__()

    return _Cursor(docs)


def _empty_cursor() -> Any:
    return _cursor([])


SAMPLE_USER = {
    "_id": "user_123",
    "email": "amiru@example.com",
    "name": "Amiru",
    "nickname": "Ami",
    "age": 22,
    "age_group": "adult",
    "role": "user",
    "is_active": True,
    "onboarding_complete": True,
    "created_at": datetime.datetime.now(datetime.UTC),
    "password_hash": None,
}


@pytest.fixture
def mock_db() -> MagicMock:
    db = MagicMock()
    db.users = MagicMock()
    db.users.find_one = AsyncMock(return_value=dict(SAMPLE_USER))
    db.token_blocklist = MagicMock()
    # require_user checks this on every authenticated request, separately
    # from list_sessions' own find() over the same collection.
    db.token_blocklist.find_one = AsyncMock(return_value=None)
    db.token_blocklist.find = MagicMock(return_value=_empty_cursor())
    db.user_sessions = MagicMock()
    db.user_sessions.find = MagicMock(return_value=_empty_cursor())
    db.user_sessions.find_one = AsyncMock(return_value=None)
    db.user_sessions.delete_one = AsyncMock()
    for name, _ in USER_DATA_COLLECTIONS:
        setattr(db, name, MagicMock())
        getattr(db, name).find = MagicMock(return_value=_empty_cursor())
        getattr(db, name).delete_many = AsyncMock(
            return_value=MagicMock(deleted_count=0)
        )
    # export_data and delete_account index the database as db[collection],
    # not db.collection — a plain MagicMock's __getitem__ returns an
    # unrelated auto-mock, so it has to be pointed at the same collection
    # mocks explicitly.
    db.__getitem__ = MagicMock(side_effect=lambda name: getattr(db, name))
    return db


@pytest.fixture
async def account_client(mock_db: MagicMock):
    from app.main import app

    app.dependency_overrides = {}
    app.dependency_overrides[get_db] = lambda: mock_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.clear()


def _auth_header() -> dict[str, str]:
    tokens = create_token_pair("user_123", "amiru@example.com", role="user")
    return {"Authorization": f"Bearer {tokens['access_token']}"}


class TestExportData:
    async def test_requires_auth(self, account_client: AsyncClient) -> None:
        response = await account_client.get("/api/v1/account/export")
        assert response.status_code in (401, 403)

    async def test_export_includes_account_and_exportable_collections(
        self, account_client: AsyncClient, mock_db: MagicMock
    ) -> None:
        mock_db.journal_entries.find = MagicMock(
            return_value=_cursor([{"_id": "j1", "user_id": "user_123", "text": "hi"}])
        )
        response = await account_client.get(
            "/api/v1/account/export", headers=_auth_header()
        )
        assert response.status_code == 200
        body = response.json()
        assert body["account"]["email"] == "amiru@example.com"
        assert "journal_entries" in body
        assert body["journal_entries"][0]["text"] == "hi"
        # Mongo's _id must not leak into an export a user downloads.
        assert "_id" not in body["journal_entries"][0]

    async def test_export_excludes_security_records(
        self, account_client: AsyncClient
    ) -> None:
        """safety_events and audit_log are still deleted on request, but
        exporting them would hand an attacker who briefly held the account
        exactly the detail they'd want. They must never appear in the
        downloadable export."""
        response = await account_client.get(
            "/api/v1/account/export", headers=_auth_header()
        )
        body = response.json()
        assert "safety_events" not in body
        assert "audit_log" not in body


class TestDeleteAccount:
    async def test_requires_auth(self, account_client: AsyncClient) -> None:
        response = await account_client.request(
            "DELETE",
            "/api/v1/account",
            json={"password": "x", "confirm": "DELETE"},
        )
        assert response.status_code in (401, 403)

    async def test_wrong_confirmation_word_is_rejected(
        self, account_client: AsyncClient, mock_db: MagicMock
    ) -> None:
        response = await account_client.request(
            "DELETE",
            "/api/v1/account",
            headers=_auth_header(),
            json={"password": "whatever", "confirm": "delete"},
        )
        assert response.status_code == 400
        mock_db.users.delete_one.assert_not_called()

    async def test_wrong_password_is_rejected(
        self, account_client: AsyncClient, mock_db: MagicMock
    ) -> None:
        import bcrypt

        mock_db.users.find_one = AsyncMock(
            return_value={
                **SAMPLE_USER,
                "password_hash": bcrypt.hashpw(b"correct-horse", bcrypt.gensalt()).decode(),
            }
        )
        response = await account_client.request(
            "DELETE",
            "/api/v1/account",
            headers=_auth_header(),
            json={"password": "wrong-password", "confirm": "DELETE"},
        )
        assert response.status_code == 401
        mock_db.users.delete_one.assert_not_called()

    async def test_correct_password_deletes_every_collection(
        self, account_client: AsyncClient, mock_db: MagicMock
    ) -> None:
        """The core promise. Every collection USER_DATA_COLLECTIONS names
        must receive a delete_many scoped to this user — not a subset, and
        not a status flag."""
        import bcrypt

        mock_db.users.find_one = AsyncMock(
            return_value={
                **SAMPLE_USER,
                "password_hash": bcrypt.hashpw(b"correct-horse", bcrypt.gensalt()).decode(),
            }
        )
        mock_db.users.delete_one = AsyncMock(
            return_value=MagicMock(deleted_count=1)
        )

        response = await account_client.request(
            "DELETE",
            "/api/v1/account",
            headers=_auth_header(),
            json={"password": "correct-horse", "confirm": "DELETE"},
        )

        assert response.status_code == 200
        body = response.json()
        assert set(body["deleted"].keys()) == {name for name, _ in USER_DATA_COLLECTIONS}
        for name, key in USER_DATA_COLLECTIONS:
            collection = getattr(mock_db, name)
            collection.delete_many.assert_awaited_once_with({key: "user_123"})
        mock_db.users.delete_one.assert_awaited_once()

    async def test_delete_revokes_every_outstanding_token_first(
        self, account_client: AsyncClient, mock_db: MagicMock
    ) -> None:
        """A token issued before the delete must not keep working after —
        otherwise a deleted account's last session lingers until its JWT
        naturally expires."""
        import bcrypt

        mock_db.users.find_one = AsyncMock(
            return_value={
                **SAMPLE_USER,
                "password_hash": bcrypt.hashpw(b"correct-horse", bcrypt.gensalt()).decode(),
            }
        )
        mock_db.users.delete_one = AsyncMock(return_value=MagicMock(deleted_count=1))
        mock_db.user_sessions.find = MagicMock(
            return_value=_cursor([{"_id": "row1", "jti": "jti-x", "refresh_jti": "ref-x"}])
        )
        mock_db.token_blocklist.update_one = AsyncMock()

        response = await account_client.request(
            "DELETE",
            "/api/v1/account",
            headers=_auth_header(),
            json={"password": "correct-horse", "confirm": "DELETE"},
        )

        assert response.status_code == 200
        assert mock_db.token_blocklist.update_one.await_count == 2
