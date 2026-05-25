"""
MongoDB connection manager — equivalent of database/index.ts.
Uses Motor (async MongoDB driver).
"""

import os
from motor.motor_asyncio import AsyncIOMotorClient
from app.utils.logger import logger

_client: AsyncIOMotorClient | None = None
_db = None


async def connect_db():
    global _client, _db
    if _client is not None:
        return

    uri = os.getenv("MONGODB_URI")
    if not uri:
        logger.log_warn("Main", "connect_db", "MONGODB_URI not set — running without persistence")
        return

    try:
        _client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
        # Verify connection
        await _client.admin.command("ping")
        try:
            _db = _client.get_default_database()
        except Exception:
            _db = _client["sgroup"]
        logger.log_info("Main", "connect_db", "Connected to MongoDB")
    except Exception as exc:
        logger.log_error("Main", "connect_db", "Failed to connect to MongoDB", {"error": exc})


async def disconnect_db():
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None
        logger.log_info("Main", "disconnect_db", "Disconnected from MongoDB")


def get_db():
    return _db
