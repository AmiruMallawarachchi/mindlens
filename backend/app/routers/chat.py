"""
MindLens WebSocket Chat Router
==============================
Real-time streaming endpoint: /ws/chat/{session_id}

Flow:
  1. Client opens WebSocket with JWT in subprotocol header
  2. Server validates JWT, checks session ownership
  3. Enforces single connection per user
  4. Message loop with 5-minute inactivity timeout
  5. Each message → Orchestrator → Streaming → WebSocket

Security:
  - JWT in header (not URL params)
  - Session ownership enforced (user can only access their own sessions)
  - Single connection per user (old connection closed)
  - 5-minute timeout on inactivity
  - All PII stripped before model calls
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from jwt.exceptions import PyJWTError as JWTError
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.agents.hosted_graph import get_hosted_orchestrator
from app.config import settings
from app.core.connection_manager import get_connection_manager
from app.db import document_id_filter, get_db
from app.middleware.auth import verify_access_token
from app.utils.logger import get_logger

from .chat_services.checkins import _send_pending_checkin
from .chat_services.flow import run_chat_message_loop
from .chat_services.persistence import _save_session_on_disconnect

logger = get_logger(__name__)

router = APIRouter()

# Message timeout (seconds)
WS_TIMEOUT = settings.WS_MESSAGE_TIMEOUT_SECONDS


@router.websocket("/chat/{session_id}")
async def websocket_chat(
    websocket: WebSocket,
    session_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    WebSocket endpoint for real-time therapy chat.

    JWT must be supplied through the secure cookie, server Authorization header,
    or the `mindlens.jwt.<token>` WebSocket subprotocol. URL query tokens are
    deliberately rejected to keep credentials out of access logs.
    Full path: /ws/chat/{session_id}

    """
    # -------------------------------------------------------------------
    # 1. Extract and validate JWT
    # -------------------------------------------------------------------
    if not _origin_allowed(websocket):
        await websocket.close(code=4003, reason="Origin not allowed")
        return

    token, selected_subprotocol = _extract_token(websocket)
    if not token:
        logger.warning("WebSocket connection rejected: no token (session=%s)", session_id)
        await websocket.close(code=4001, reason="Missing authorization token")
        return

    try:
        jwt_user = verify_access_token(token)
    except JWTError as exc:
        logger.warning("WebSocket connection rejected: invalid token (%s)", exc)
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    user_id = jwt_user.id

    # -------------------------------------------------------------------
    # 2. Verify session ownership
    # -------------------------------------------------------------------
    session = await db.sessions.find_one({
        "session_id": session_id,
        "user_id": user_id,
    })
    if not session:
        logger.warning(
            "WebSocket connection rejected: session not found or not owned "
            "(session=%s, user=%s)", session_id, user_id
        )
        await websocket.close(code=4003, reason="Forbidden: session not found")
        return

    # -------------------------------------------------------------------
    # 3. ConnectionManager: accept and enforce single connection
    # -------------------------------------------------------------------
    conn_manager = get_connection_manager()
    connected = await conn_manager.connect(
        websocket, user_id, session_id, subprotocol=selected_subprotocol
    )
    if not connected:
        logger.warning("WebSocket connection failed for user %s", user_id)
        await websocket.close(code=1013, reason="Try again later")
        return

    # Initialize orchestrator
    orchestrator = get_hosted_orchestrator()

    # Load user profile for personalization
    user = await db.users.find_one(document_id_filter(user_id))
    user_name = user.get("nickname", user.get("name", "friend")) if user else "friend"

    # Send welcome / check-in if pending
    await _send_pending_checkin(db, user_id, conn_manager)

    logger.info(
        "WebSocket chat started: user=%s session=%s",
        user_id, session_id,
    )

    # -------------------------------------------------------------------
    # 4. Message loop
    # -------------------------------------------------------------------
    try:
        await run_chat_message_loop(
            websocket=websocket,
            db=db,
            session_id=session_id,
            user_id=user_id,
            user_name=user_name,
            conn_manager=conn_manager,
            orchestrator=orchestrator,
        )
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: user=%s session=%s", user_id, session_id)
    except Exception:
        logger.exception("WebSocket loop error: user=%s session=%s", user_id, session_id)
    finally:
        # Cleanup
        await conn_manager.disconnect(user_id)
        await _save_session_on_disconnect(db, session_id, user_id)
        logger.info("WebSocket cleanup complete: user=%s", user_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_token(websocket: WebSocket) -> tuple[str | None, str | None]:
    """Extract the JWT, and the subprotocol to echo on accept.

    These are two separate questions and conflating them broke every browser
    client. RFC 6455: if the client offers a subprotocol, the server must
    echo one back, and browsers abort the handshake when it doesn't --
    "Sent non-empty 'Sec-WebSocket-Protocol' header but no response was
    received". The frontend always offers `mindlens.jwt.<token>`, because a
    browser cannot set headers on a WebSocket.

    So the offered protocol is resolved first and returned no matter which
    source the token comes from. Previously the cookie branch returned early
    with None, meaning the echo only happened when there was no cookie.

    That hid the bug in exactly the wrong place. Deployed, the frontend and
    backend are different sites, the SameSite=lax cookie is not sent on the
    handshake, and the subprotocol branch runs and echoes. On localhost both
    are the same site, the cookie is sent, and the handshake fails -- so chat
    worked in production and was broken in local development.
    """
    offered = websocket.headers.get("sec-websocket-protocol", "")
    subprotocol_token: str | None = None
    selected: str | None = None
    for protocol in (item.strip() for item in offered.split(",")):
        if protocol.startswith("mindlens.jwt."):
            subprotocol_token = protocol.removeprefix("mindlens.jwt.")
            selected = protocol
            break

    cookie_token = websocket.cookies.get("access_token")
    if cookie_token:
        return cookie_token, selected

    auth = websocket.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:], selected

    return subprotocol_token, selected


def _origin_allowed(websocket: WebSocket) -> bool:
    """Reject browser WebSocket handshakes from untrusted origins."""
    origin = websocket.headers.get("origin")
    return not origin or origin in settings.cors_origins
