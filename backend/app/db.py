# backend/app/db.py
"""MongoDB Atlas connection manager."""

from __future__ import annotations

from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class Database:
    client: Optional[AsyncIOMotorClient] = None


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

    logger.info("Database indexes created")


async def close_db() -> None:
    """Close MongoDB client."""
    if db.client:
        db.client.close()
        db.client = None
        logger.info("MongoDB connection closed")


# Alias for backward compatibility
disconnect_db = close_db


def get_database():
    """Return the database instance. Raises if not connected."""
    if db.client is None:
        raise RuntimeError("Database not connected. Call connect_db() first.")
    return db.client[settings.mongodb_db_name]


# Accessor for main.py readiness probe — must be a function,
# NOT a snapshot, because db.client is None at import time.
def get_db_client() -> AsyncIOMotorClient | None:
    """Return the live Motor client (or None if not yet connected)."""
    return db.client