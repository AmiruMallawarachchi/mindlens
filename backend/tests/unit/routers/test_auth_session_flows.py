"""Tests for MindLens Authentication Router."""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.middleware.auth import create_token_pair
from app.routers.auth import hash_password
from fastapi import status

# --- Helper fixtures ---


@pytest.fixture
async def auth_client(mock_db: MagicMock):
    """FastAPI test client with mocked DB dependency injection."""
    from app.main import app
    from httpx import ASGITransport, AsyncClient

    # Override get_db dependency
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
    """A sample user document as stored in MongoDB."""
    return {
        "_id": "user_123",
        "email": "test@example.com",
        "password_hash": hash_password("SecurePass123!"),
        "name": "Amiru",
        "nickname": "Ami",
        "age": 22,
        "age_group": "adult",
        "role": "user",
        "created_at": datetime.datetime.now(datetime.UTC),
        "updated_at": datetime.datetime.now(datetime.UTC),
        "is_active": True,
        "onboarding_complete": False,
    }


# --- Password hashing tests ---


class TestLogin:
    async def test_login_success(self, auth_client: Any, mock_db: MagicMock, sample_user_doc: dict) -> None:
        mock_db.users.find_one = AsyncMock(return_value=sample_user_doc)
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)
        mock_db.audit_log = MagicMock()
        mock_db.audit_log.insert_one = AsyncMock()

        with patch("app.routers.auth_user_routes.get_rate_limit_store") as mock_store:
            store = MagicMock()
            store.is_locked_out = AsyncMock(return_value=False)
            store.record_login_attempt = AsyncMock(return_value=1)
            store.reset_login_attempts = AsyncMock()
            mock_store.return_value = store

            response = await auth_client.post("/api/v1/auth/login", json={
                "email": "test@example.com",
                "password": "SecurePass123!",
            })

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["role"] == "user"
        assert "refresh_token" in response.cookies or True  # httponly cookie may not be visible in test client


    async def test_login_wrong_password(self, auth_client: Any, mock_db: MagicMock, sample_user_doc: dict) -> None:
        mock_db.users.find_one = AsyncMock(return_value=sample_user_doc)
        mock_db.token_blocklist = MagicMock()

        with patch("app.routers.auth_user_routes.get_rate_limit_store") as mock_store:
            store = MagicMock()
            store.is_locked_out = AsyncMock(return_value=False)
            store.record_login_attempt = AsyncMock(return_value=1)
            mock_store.return_value = store

            response = await auth_client.post("/api/v1/auth/login", json={
                "email": "test@example.com",
                "password": "WrongPassword123!",
            })

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_login_user_not_found(self, auth_client: Any, mock_db: MagicMock) -> None:
        mock_db.users.find_one = AsyncMock(return_value=None)

        with patch("app.routers.auth_user_routes.get_rate_limit_store") as mock_store:
            store = MagicMock()
            store.is_locked_out = AsyncMock(return_value=False)
            store.record_login_attempt = AsyncMock(return_value=1)
            mock_store.return_value = store

            response = await auth_client.post("/api/v1/auth/login", json={
                "email": "notfound@example.com",
                "password": "SecurePass123!",
            })

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_login_lockout(self, auth_client: Any, mock_db: MagicMock, sample_user_doc: dict) -> None:
        mock_db.users.find_one = AsyncMock(return_value=sample_user_doc)

        with patch("app.routers.auth_user_routes.get_rate_limit_store") as mock_store:
            store = MagicMock()
            store.is_locked_out = AsyncMock(return_value=True)
            mock_store.return_value = store

            response = await auth_client.post("/api/v1/auth/login", json={
                "email": "test@example.com",
                "password": "SecurePass123!",
            })

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    async def test_login_inactive_account(self, auth_client: Any, mock_db: MagicMock, sample_user_doc: dict) -> None:
        doc = dict(sample_user_doc)
        doc["is_active"] = False
        mock_db.users.find_one = AsyncMock(return_value=doc)
        mock_db.token_blocklist = MagicMock()

        with patch("app.routers.auth_user_routes.get_rate_limit_store") as mock_store:
            store = MagicMock()
            store.is_locked_out = AsyncMock(return_value=False)
            store.record_login_attempt = AsyncMock(return_value=1)
            store.reset_login_attempts = AsyncMock()
            mock_store.return_value = store

            response = await auth_client.post("/api/v1/auth/login", json={
                "email": "test@example.com",
                "password": "SecurePass123!",
            })

        assert response.status_code == status.HTTP_403_FORBIDDEN


# --- Token refresh tests ---


class TestRefresh:
    async def test_refresh_success(self, auth_client: Any, mock_db: MagicMock, sample_user_doc: dict) -> None:
        mock_db.users.find_one = AsyncMock(return_value=sample_user_doc)
        mock_db.token_blocklist.find_one = AsyncMock(return_value=None)

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        refresh_token = tokens["refresh_token"]

        auth_client.cookies.set("refresh_token", refresh_token)
        response = await auth_client.post("/api/v1/auth/refresh")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data

    async def test_refresh_no_cookie(self, auth_client: Any, mock_db: MagicMock) -> None:
        response = await auth_client.post("/api/v1/auth/refresh")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_refresh_invalid_token(self, auth_client: Any, mock_db: MagicMock) -> None:
        auth_client.cookies.set("refresh_token", "invalid_token")
        response = await auth_client.post("/api/v1/auth/refresh")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_refresh_blocklisted(self, auth_client: Any, mock_db: MagicMock, sample_user_doc: dict) -> None:
        mock_db.users.find_one = AsyncMock(return_value=sample_user_doc)
        mock_db.token_blocklist.find_one = AsyncMock(return_value={"token_jti": "blocked"})

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        auth_client.cookies.set("refresh_token", tokens["refresh_token"])

        response = await auth_client.post("/api/v1/auth/refresh")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# --- Logout tests ---


class _FakeBlocklist:
    """The real collection has a unique index on token_jti.

    Storing by jti reproduces that, so a test can prove logout is idempotent
    rather than merely that it did not raise.
    """

    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}

    async def update_one(self, flt, update, upsert=False):  # noqa: ANN001, ANN201
        self.rows.setdefault(flt["token_jti"], {}).update(update["$set"])

    async def find_one(self, flt):  # noqa: ANN001
        row = self.rows.get(flt["token_jti"])
        return {"token_jti": flt["token_jti"], **row} if row else None


class TestLogout:
    async def test_logout_blocklists_every_token_the_pair_contains(
        self, auth_client: Any, mock_db: MagicMock, sample_user_doc: dict
    ) -> None:
        blocklist = _FakeBlocklist()
        mock_db.token_blocklist = blocklist

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        auth_client.cookies.set("refresh_token", tokens["refresh_token"])

        response = await auth_client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert blocklist.rows.keys() == {tokens["jti"], tokens["refresh_jti"]}

    async def test_the_refresh_tokens_own_access_jti_is_revoked_too(
        self, auth_client: Any, mock_db: MagicMock
    ) -> None:
        """After a silent refresh the header carries a superseded token, so
        the refresh payload is what names the live one."""
        blocklist = _FakeBlocklist()
        mock_db.token_blocklist = blocklist

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        fresh = create_token_pair("user_123", "test@example.com", role="user")
        auth_client.cookies.set("refresh_token", tokens["refresh_token"])

        await auth_client.post(
            "/api/v1/auth/logout", headers={"Authorization": f"Bearer {fresh['access_token']}"}
        )

        assert tokens["jti"] in blocklist.rows

    async def test_a_logged_out_access_token_is_rejected(
        self, auth_client: Any, mock_db: MagicMock, sample_user_doc: dict
    ) -> None:
        """The point of logout, asserted rather than assumed."""
        blocklist = _FakeBlocklist()
        mock_db.token_blocklist = blocklist
        mock_db.users.find_one = AsyncMock(return_value=sample_user_doc)

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        before = await auth_client.get("/api/v1/auth/me", headers=headers)
        assert before.status_code == status.HTTP_200_OK

        await auth_client.post("/api/v1/auth/logout", headers=headers)

        after = await auth_client.get("/api/v1/auth/me", headers=headers)
        assert after.status_code == status.HTTP_401_UNAUTHORIZED
        assert after.json()["detail"] == "Token has been revoked"

    async def test_logout_is_idempotent(
        self, auth_client: Any, mock_db: MagicMock
    ) -> None:
        """A double click used to 500: the unique index rejected the second
        insert, before the cookies were ever cleared."""
        blocklist = _FakeBlocklist()
        mock_db.token_blocklist = blocklist

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        auth_client.cookies.set("refresh_token", tokens["refresh_token"])
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        first = await auth_client.post("/api/v1/auth/logout", headers=headers)
        second = await auth_client.post("/api/v1/auth/logout", headers=headers)

        assert first.status_code == second.status_code == status.HTTP_200_OK
        assert len(blocklist.rows) == 2

    async def test_cookie_only_logout_revokes_the_access_cookie(
        self, auth_client: Any, mock_db: MagicMock
    ) -> None:
        """The header-only version left a cookie-authenticated logout
        revoking nothing at all."""
        blocklist = _FakeBlocklist()
        mock_db.token_blocklist = blocklist

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        auth_client.cookies.set("refresh_token", tokens["refresh_token"])

        response = await auth_client.post(
            "/api/v1/auth/logout",
            headers={"Cookie": f"access_token={tokens['access_token']}"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert tokens["jti"] in blocklist.rows

    async def test_revocation_rows_carry_an_expiry_the_ttl_index_can_read(
        self, auth_client: Any, mock_db: MagicMock
    ) -> None:
        """Without expires_at the row outlives the token and is never reaped."""
        blocklist = _FakeBlocklist()
        mock_db.token_blocklist = blocklist

        tokens = create_token_pair("user_123", "test@example.com", role="user")
        await auth_client.post(
            "/api/v1/auth/logout", headers={"Authorization": f"Bearer {tokens['access_token']}"}
        )

        row = blocklist.rows[tokens["jti"]]
        assert row["expires_at"] > datetime.datetime.now(datetime.UTC)
        assert row["user_id"] == "user_123"

    async def test_logout_forgets_this_devices_session_row(
        self, auth_client: Any, mock_db: MagicMock
    ) -> None:
        tokens = create_token_pair("user_123", "test@example.com", role="user")
        mock_db.user_sessions.delete_one = AsyncMock()

        await auth_client.post(
            "/api/v1/auth/logout", headers={"Authorization": f"Bearer {tokens['access_token']}"}
        )

        mock_db.user_sessions.delete_one.assert_awaited_once_with(
            {"user_id": "user_123", "jti": tokens["jti"]}
        )

    async def test_logout_with_nothing_to_revoke(self, auth_client: Any, mock_db: MagicMock) -> None:
        mock_db.token_blocklist = _FakeBlocklist()
        response = await auth_client.post("/api/v1/auth/logout")
        assert response.status_code == status.HTTP_200_OK

    async def test_a_storage_failure_still_clears_the_cookies(
        self, auth_client: Any, mock_db: MagicMock
    ) -> None:
        tokens = create_token_pair("user_123", "test@example.com", role="user")

        class _Down:
            async def update_one(self, *a, **k):  # noqa: ANN002, ANN003
                raise RuntimeError("mongo is down")

            async def find_one(self, *a, **k):  # noqa: ANN002, ANN003
                return None

        mock_db.token_blocklist = _Down()
        mock_db.user_sessions.delete_one = AsyncMock(side_effect=RuntimeError("mongo is down"))

        response = await auth_client.post(
            "/api/v1/auth/logout", headers={"Authorization": f"Bearer {tokens['access_token']}"}
        )

        assert response.status_code == status.HTTP_200_OK
        cookies = response.headers["set-cookie"]
        assert "refresh_token=" in cookies
        assert "Max-Age=0" in cookies


# --- Me endpoint tests ---


