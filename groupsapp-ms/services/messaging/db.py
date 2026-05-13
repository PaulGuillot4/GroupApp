"""
MongoDB connection management — Motor (async) + PyMongo (sync).

Provides two clients:
  - Motor  (AsyncIOMotorClient) → WebSocket consumers (async context)
  - PyMongo (MongoClient)       → gRPC servicer       (sync / threaded)

IMPORTANT: Motor client is created lazily on first use within the running
event loop (Daphne's).  Do NOT create it at import time or inside
asyncio.run() — that would bind it to a short-lived loop.
"""

import os

from pymongo import MongoClient, ASCENDING, DESCENDING

MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
MONGO_PORT = os.getenv("MONGO_PORT", "27017")
MONGO_DB = os.getenv("MONGO_DB", "groupsapp_messages")
MONGO_USER = os.getenv("MONGO_USER", "admin")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD", "groupsapp_mongo")

MONGO_URI = (
    f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}"
    f"@{MONGO_HOST}:{MONGO_PORT}/{MONGO_DB}?authSource=admin"
)


# ── Async client (Motor) ─────────────────────────────────────
# Lazy import + lazy init so it binds to the *current* event loop.

_motor_client = None


def get_async_db():
    """Return the Motor database handle (lazy singleton).

    Must be called from within a running asyncio event loop (e.g. Daphne).
    """
    global _motor_client
    if _motor_client is None:
        from motor.motor_asyncio import AsyncIOMotorClient
        _motor_client = AsyncIOMotorClient(MONGO_URI)
    return _motor_client[MONGO_DB]


# ── Sync client (PyMongo) ────────────────────────────────────

_pymongo_client: MongoClient | None = None


def get_sync_db():
    """Return the PyMongo database handle (lazy singleton)."""
    global _pymongo_client
    if _pymongo_client is None:
        _pymongo_client = MongoClient(MONGO_URI)
    return _pymongo_client[MONGO_DB]


# ── Index management (sync — safe to call from any context) ──

def ensure_indexes():
    """Create indexes on first startup (idempotent). Uses PyMongo (sync)."""
    db = get_sync_db()

    msgs = db.messages
    msgs.create_index(
        [("type", ASCENDING), ("group_id", ASCENDING), ("created_at", DESCENDING)],
        name="idx_group_history",
    )
    msgs.create_index(
        [("type", ASCENDING), ("channel_id", ASCENDING), ("created_at", DESCENDING)],
        name="idx_channel_history",
    )
    msgs.create_index(
        [
            ("type", ASCENDING),
            ("sender_id", ASCENDING),
            ("receiver_id", ASCENDING),
            ("created_at", DESCENDING),
        ],
        name="idx_private_history",
    )
    msgs.create_index(
        [("sender_id", ASCENDING), ("created_at", DESCENDING)],
        name="idx_sender_convos",
    )

    statuses = db.message_statuses
    statuses.create_index(
        [("message_id", ASCENDING), ("user_id", ASCENDING)],
        name="idx_status_unique",
        unique=True,
    )
    statuses.create_index(
        [("user_id", ASCENDING), ("status", ASCENDING)],
        name="idx_user_status",
    )

    print("[db] MongoDB indexes ensured", flush=True)
