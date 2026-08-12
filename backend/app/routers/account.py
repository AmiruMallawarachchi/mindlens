"""
MindLens Account Router
=======================
The controls that make the privacy promise real rather than stated:

  - See every device signed in, and sign any of them out.
  - Download everything MindLens holds about you.
  - Delete the account, and actually have the data go.

Design notes
------------
Deliberately *no* raw IP addresses are stored for sessions. auth.py already
hashes IPs for the audit log, and an app whose pitch is "your words stay
yours" should not start keeping a location history to power a settings
screen. Device label plus sign-in time is enough for a user to recognise a
session they don't want.

Deletion is a hard delete, not a soft flag. A wellbeing app that keeps your
journal after you asked it not to has broken the only promise that matters.
"""

from __future__ import annotations

import datetime
from typing import Any

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.db import document_id_filter, get_db
from app.middleware.auth import (
    get_request_access_token,
    require_user,
    verify_access_token,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


def current_jti(request: Request) -> str:
    """The token id this request arrived on, so "this device" can be marked
    in the session list and skipped when signing the others out.

    require_user has already validated the token by the time any route using
    this runs, so a failure here is a programming error, not an auth path.
    """
    token = get_request_access_token(request)
    if not token:
        return ""
    try:
        return verify_access_token(token).jti
    except Exception:  # pragma: no cover - require_user rejects these first
        return ""


# Every collection that holds something belonging to a user. Kept in one
# place so export and delete can never drift apart — a new collection that
# stores user data must be added here or both features are silently wrong.
USER_DATA_COLLECTIONS: list[tuple[str, str]] = [
    ("user_memory", "user_id"),
    ("sessions", "user_id"),
    ("journal_entries", "user_id"),
    ("mood_logs", "user_id"),
    ("progress_insights", "user_id"),
    ("pending_checkins", "user_id"),
    ("safety_events", "user_id"),
    ("audit_log", "user_id"),
]

# Collections a user is allowed to *read back* in an export. safety_events
# and audit_log are security records rather than personal content; they are
# still deleted on request, but exporting them would hand over the exact
# detail an attacker who briefly held an account would want.
EXPORTABLE = {"user_memory", "sessions", "journal_entries", "mood_logs", "progress_insights"}


def device_label(user_agent: str | None) -> str:
    """A short, human-recognisable device name. Intentionally coarse — enough
    to answer "is that me?", not enough to fingerprint anyone."""
    ua = (user_agent or "").lower()
    if not ua:
        return "Unknown device"
    if "android" in ua:
        os_name = "Android"
    elif "iphone" in ua or "ipad" in ua or "ios" in ua:
        os_name = "iOS"
    elif "mac os" in ua or "macintosh" in ua:
        os_name = "Mac"
    elif "windows" in ua:
        os_name = "Windows"
    elif "linux" in ua:
        os_name = "Linux"
    else:
        os_name = "Unknown OS"

    if "edg/" in ua:
        browser = "Edge"
    elif "opr/" in ua or "opera" in ua:
        browser = "Opera"
    elif "chrome" in ua:
        browser = "Chrome"
    elif "firefox" in ua:
        browser = "Firefox"
    elif "safari" in ua:
        browser = "Safari"
    else:
        browser = "Browser"

    return f"{browser} on {os_name}"


async def record_login_session(
    db: AsyncIOMotorDatabase,
    user_id: str,
    jti: str,
    refresh_jti: str,
    request: Request,
) -> None:
    """Remember that this token pair belongs to a signed-in device.

    Best-effort: a failure here must never block a login, because being
    unable to *log* a session is not a reason to stop someone reaching
    support.
    """
    try:
        await db.user_sessions.insert_one({
            "user_id": user_id,
            "jti": jti,
            "refresh_jti": refresh_jti,
            "device": device_label(request.headers.get("user-agent")),
            "created_at": datetime.datetime.now(datetime.UTC),
        })
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Could not record login session: %s", exc)


# --- Sessions ---------------------------------------------------------------

@router.get("/sessions", summary="List devices currently signed in")
async def list_sessions(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_user),
    jti: str = Depends(current_jti),
):
    user_id = str(current_user["_id"])
    cursor = db.user_sessions.find({"user_id": user_id}).sort("created_at", -1)
    rows = await cursor.to_list(length=100)

    blocked = {
        doc["token_jti"]
        async for doc in db.token_blocklist.find({}, {"token_jti": 1})
    }

    return [
        {
            "jti": row["jti"],
            "device": row.get("device", "Unknown device"),
            "created_at": row.get("created_at"),
            "current": row["jti"] == jti,
        }
        for row in rows
        if row["jti"] not in blocked
    ]


async def _revoke(db: AsyncIOMotorDatabase, user_id: str, row: dict[str, Any]) -> None:
    """Blocklist both halves of a session's token pair, then forget the row."""
    now = datetime.datetime.now(datetime.UTC)
    for key in ("jti", "refresh_jti"):
        if row.get(key):
            await db.token_blocklist.update_one(
                {"token_jti": row[key]},
                {"$set": {"token_jti": row[key], "user_id": user_id, "revoked_at": now}},
                upsert=True,
            )
    await db.user_sessions.delete_one({"_id": row["_id"]})


@router.delete("/sessions/{jti}", summary="Sign out one device")
async def revoke_session(
    jti: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_user),
):
    user_id = str(current_user["_id"])
    row = await db.user_sessions.find_one({"user_id": user_id, "jti": jti})
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    await _revoke(db, user_id, row)
    return {"message": "Signed out on that device"}


@router.post("/sessions/revoke-others", summary="Sign out every other device")
async def revoke_other_sessions(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_user),
    jti: str = Depends(current_jti),
):
    user_id = str(current_user["_id"])
    rows = await db.user_sessions.find({"user_id": user_id}).to_list(length=200)
    count = 0
    for row in rows:
        if row["jti"] == jti:
            continue
        await _revoke(db, user_id, row)
        count += 1
    return {"message": "Other devices signed out", "revoked": count}


# --- Export -----------------------------------------------------------------

@router.get("/export", summary="Download everything MindLens holds about you")
async def export_data(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_user),
):
    """Everything the user can meaningfully read back, as one JSON document."""
    user_id = str(current_user["_id"])

    export: dict[str, Any] = {
        "exported_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "account": {
            "email": current_user.get("email"),
            "name": current_user.get("name"),
            "nickname": current_user.get("nickname"),
            "age": current_user.get("age"),
            "created_at": current_user.get("created_at"),
        },
    }

    for collection, key in USER_DATA_COLLECTIONS:
        if collection not in EXPORTABLE:
            continue
        rows = await db[collection].find({key: user_id}).to_list(length=5000)
        for row in rows:
            row.pop("_id", None)
        export[collection] = rows

    return export


# --- Deletion ---------------------------------------------------------------

class DeleteAccountRequest(BaseModel):
    password: str = Field(..., min_length=1)
    # Typing the word is a deliberate speed bump on an irreversible action.
    confirm: str = Field(..., description='Must be exactly "DELETE"')


@router.delete("", summary="Permanently delete this account and all its data")
async def delete_account(
    req: DeleteAccountRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_user),
):
    """Hard delete. There is no recovery, and that is the point."""
    if req.confirm != "DELETE":
        raise HTTPException(status_code=400, detail='Type DELETE to confirm.')

    stored = current_user.get("password_hash") or current_user.get("hashed_password") or ""
    if not stored or not bcrypt.checkpw(req.password.encode(), stored.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="That password isn't right.",
        )

    user_id = str(current_user["_id"])
    deleted: dict[str, int] = {}
    for collection, key in USER_DATA_COLLECTIONS:
        result = await db[collection].delete_many({key: user_id})
        deleted[collection] = result.deleted_count

    # Revoke every outstanding token before the account row goes, so no
    # already-issued JWT can outlive the deletion.
    rows = await db.user_sessions.find({"user_id": user_id}).to_list(length=500)
    for row in rows:
        await _revoke(db, user_id, row)

    await db.users.delete_one(document_id_filter(user_id))

    logger.info("Account deleted: %s (%s)", user_id, deleted)
    return {"message": "Your account and everything in it has been deleted.", "deleted": deleted}
