"""
Session model — equivalent of database/models/Session.ts.
Stores conversation history per Facebook user with 30-minute TTL.
"""

from datetime import datetime
from app.database.connection import get_db

COLLECTION = "sessions"
TTL_SECONDS = 1800  # 30 minutes


async def ensure_indexes():
    """Create TTL index on updatedAt so sessions expire after 30 minutes."""
    db = get_db()
    if db is None:
        return
    col = db[COLLECTION]
    await col.create_index("facebookId", unique=True)
    await col.create_index("updatedAt", expireAfterSeconds=TTL_SECONDS)


async def get_session(facebook_id: str) -> dict:
    db = get_db()
    if db is None:
        return {"facebookId": facebook_id, "history": []}
    doc = await db[COLLECTION].find_one({"facebookId": facebook_id})
    if doc is None:
        return {"facebookId": facebook_id, "history": []}
    return doc


async def save_session(facebook_id: str, history: list[dict]):
    db = get_db()
    if db is None:
        return
    await db[COLLECTION].update_one(
        {"facebookId": facebook_id},
        {"$set": {"history": history, "updatedAt": datetime.utcnow()}},
        upsert=True,
    )
