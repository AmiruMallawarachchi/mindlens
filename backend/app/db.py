# backend/app/db.py
"""MongoDB Atlas connection manager."""

from __future__ import annotations

from typing import Optional  # noqa: F401

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
    db.client = AsyncIOMotorClient(
        settings.mongodb_url,
        tls=True,
        tlsAllowInvalidCertificates=True,
    )
    logger.info("Connected to MongoDB: %s", settings.mongodb_db_name)

    database = db.client[settings.mongodb_db_name]

    await database.users.create_index("email", unique=True)
    await database.sessions.create_index("user_id")
    await database.sessions.create_index("created_at")
    await database.mood_logs.create_index([("user_id", 1), ("timestamp", -1)])
    await database.safety_events.create_index("timestamp")
    await database.token_blocklist.create_index("token_jti", unique=True)
    await database.user_memory.create_index("user_id", unique=True)
    await database.pending_checkins.create_index([("user_id", 1), ("delivered", 1)])

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
