# backend/app/db.py
"""MongoDB Atlas connection manager."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class Database:
    client: AsyncIOMotorClient | None = None


db = Database()

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def connect_db() -> None:
    """Create MongoDB client, verify connection, and build indexes."""
    mongo_url = settings.mongodb_url
    is_local = any(
        mongo_url.startswith(p) for p in ("mongodb://localhost", "mongodb://127.0.0.1")
    )

    client_kwargs: dict = {
        "serverSelectionTimeoutMS": 10000,
        "retryWrites": True,
    }

    # Parse connection string to avoid duplicating or conflicting with
    # options that are already in the URI.
    parsed = urlparse(mongo_url)
    existing_params = {k.lower() for k in parse_qs(parsed.query).keys()}

    if not is_local:
        # If the user already has tlsAllowInvalidCertificates in their URI,
        # we skip all other TLS tweaks to avoid PyMongo conflicts.
        if "tlsallowinvalidcertificates" not in existing_params:
            if "tls" not in existing_params and "ssl" not in existing_params:
                client_kwargs["tls"] = True

            # Windows + OpenSSL 3.0 workaround: disable OCSP endpoint check
            # which causes TLSV1_ALERT_INTERNAL_ERROR on Windows with Python 3.11+
            if "tlsdisableocspendpointcheck" not in existing_params:
                client_kwargs["tlsDisableOCSPEndpointCheck"] = True

    db.client = AsyncIOMotorClient(mongo_url, **client_kwargs)

    # Fail fast — verify connectivity before building indexes
    try:
        await db.client.admin.command("ping")
    except Exception as exc:
        logger.error("MongoDB connection failed: %s", type(exc).__name__)
        raise RuntimeError(
            "Failed to connect to MongoDB. Check the configured network access, "
            "credentials, TLS settings, and database availability."
        ) from exc

    logger.info("Connected to MongoDB: %s", settings.mongodb_db_name)
    database = db.client[settings.mongodb_db_name]

    await database.users.create_index("email", unique=True)
    await database.sessions.create_index("user_id")
    await database.sessions.create_index("session_id", unique=True)
    await database.sessions.create_index("created_at")
    await database.mood_logs.create_index([("user_id", 1), ("timestamp", -1)])
    await database.safety_events.create_index("timestamp")
    await database.audit_log.create_index("timestamp")
    await database.audit_log.create_index([("user_id", 1), ("timestamp", -1)])
    await database.token_blocklist.create_index("token_jti", unique=True)
    await database.token_blocklist.create_index("expires_at", expireAfterSeconds=0)
    await database.user_memory.create_index("user_id", unique=True)
    await database.pending_checkins.create_index([("user_id", 1), ("delivered", 1)])
    await database.pending_checkins.create_index("expires_at", expireAfterSeconds=0)
    await database.journal_entries.create_index("entry_id", unique=True)
    await database.journal_entries.create_index([("user_id", 1), ("created_at", -1)])
    await database.progress_insights.create_index("user_id", unique=True)

    logger.info("Database indexes created")


async def close_db() -> None:
    """Close MongoDB client."""
    if db.client:
        db.client.close()
        db.client = None
    logger.info("MongoDB connection closed")


# Alias for backward compatibility
disconnect_db = close_db


def get_database() -> AsyncIOMotorDatabase:
    """Return the database instance. Raises if not connected."""
    if db.client is None:
        raise RuntimeError("Database not connected. Call connect_db() first.")
    return db.client[settings.mongodb_db_name]


# FastAPI dependency — returns the database for injection
async def get_db() -> AsyncIOMotorDatabase:
    """FastAPI dependency that yields the live database."""
    return get_database()


# Collection accessors (for cleaner code in routers)
async def get_user_collection():
    """Return the users collection."""
    return get_database().users


async def get_blocklist_collection():
    """Return the token blocklist collection."""
    return get_database().token_blocklist


async def get_sessions_collection():
    """Return the sessions collection."""
    return get_database().sessions


async def get_memory_collection():
    """Return the user memory collection."""
    return get_database().user_memory


# Accessor for main.py readiness probe — must be a function,
# NOT a snapshot, because db.client is None at import time.
def get_db_client() -> AsyncIOMotorClient | None:
    """Return the live Motor client (or None if not yet connected)."""
    return db.client


def document_id_filter(document_id: str) -> dict[str, object]:
    """Match both new string IDs and legacy MongoDB ObjectId records."""
    if ObjectId.is_valid(document_id):
        return {"_id": {"$in": [document_id, ObjectId(document_id)]}}
    return {"_id": document_id}
