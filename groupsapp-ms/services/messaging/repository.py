"""
Message repository — data-access layer for MongoDB.

Async methods use Motor   → called from WebSocket consumers.
Sync  methods use PyMongo → called from gRPC servicer.
"""

import uuid
from datetime import datetime, timezone

from db import get_async_db, get_sync_db


# ── Helpers ──────────────────────────────────────────────────

def _new_id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _msg_doc(data: dict) -> dict:
    """Build a normalised message document with defaults."""
    return {
        "_id": data.get("id") or _new_id(),
        "sender_id": data.get("sender_id", ""),
        "sender_username": data.get("sender_username", ""),
        "type": data.get("type", ""),
        "group_id": data.get("group_id", ""),
        "channel_id": data.get("channel_id", ""),
        "receiver_id": data.get("receiver_id", ""),
        "content": data.get("content", ""),
        "message_type": data.get("message_type", "text"),
        "file_url": data.get("file_url", ""),
        "created_at": data.get("created_at") or _now(),
    }


# ─────────────────────────────────────────────────────────────
# Async API  (Motor — WebSocket consumers)
# ─────────────────────────────────────────────────────────────

async def insert_message(data: dict) -> dict:
    """Insert a message and return the full document."""
    doc = _msg_doc(data)
    db = get_async_db()
    await db.messages.insert_one(doc)
    return doc


async def upsert_status(message_id: str, user_id: str, status: str) -> None:
    """Create or update a per-user message status (delivered / read)."""
    db = get_async_db()
    await db.message_statuses.update_one(
        {"message_id": message_id, "user_id": user_id},
        {"$set": {"status": status, "updated_at": _now()}},
        upsert=True,
    )


async def get_unread_for_room(
    room_type: str, room_id: str, user_id: str
) -> list[dict]:
    """Return messages in a room not yet delivered/read by *user_id*."""
    db = get_async_db()

    if room_type == "group":
        msg_filter = {"type": "group", "group_id": room_id, "sender_id": {"$ne": user_id}}
    elif room_type == "channel":
        msg_filter = {"type": "channel", "channel_id": room_id, "sender_id": {"$ne": user_id}}
    elif room_type == "private":
        msg_filter = {"type": "private", "sender_id": room_id, "receiver_id": user_id}
    else:
        return []

    # IDs already acknowledged by this user
    acked_cursor = db.message_statuses.find(
        {"user_id": user_id, "status": {"$in": ["delivered", "read"]}},
        {"message_id": 1},
    )
    acked_ids = {doc["message_id"] async for doc in acked_cursor}

    result = []
    async for msg in db.messages.find(msg_filter):
        if msg["_id"] not in acked_ids:
            result.append(msg)
    return result


async def get_sender_id(message_id: str) -> str | None:
    """Look up the sender_id of a message."""
    db = get_async_db()
    doc = await db.messages.find_one({"_id": message_id}, {"sender_id": 1})
    return doc["sender_id"] if doc else None


# ─────────────────────────────────────────────────────────────
# Sync API  (PyMongo — gRPC servicer)
# ─────────────────────────────────────────────────────────────

def get_group_history_sync(group_id: str, limit: int = 50) -> list[dict]:
    db = get_sync_db()
    return list(
        db.messages
        .find({"type": "group", "group_id": group_id})
        .sort("created_at", -1)
        .limit(limit)
    )


def get_channel_history_sync(channel_id: str, limit: int = 50) -> list[dict]:
    db = get_sync_db()
    return list(
        db.messages
        .find({"type": "channel", "channel_id": channel_id})
        .sort("created_at", -1)
        .limit(limit)
    )


def get_private_history_sync(
    user_id: str, other_id: str, limit: int = 50
) -> list[dict]:
    db = get_sync_db()
    return list(
        db.messages
        .find({
            "type": "private",
            "$or": [
                {"sender_id": user_id, "receiver_id": other_id},
                {"sender_id": other_id, "receiver_id": user_id},
            ],
        })
        .sort("created_at", -1)
        .limit(limit)
    )


def list_conversations_sync(user_id: str) -> list[dict]:
    """Aggregate all conversations (group / channel / private) for a user."""
    db = get_sync_db()
    convos: list[dict] = []

    # ── Groups & channels where the user sent messages ──
    for row in db.messages.aggregate([
        {"$match": {"type": {"$in": ["group", "channel"]}, "sender_id": user_id}},
        {"$group": {
            "_id": {"type": "$type", "group_id": "$group_id", "channel_id": "$channel_id"},
            "last_at": {"$max": "$created_at"},
        }},
        {"$sort": {"last_at": -1}},
    ]):
        msg_type = row["_id"]["type"]
        cid = row["_id"]["group_id"] if msg_type == "group" else row["_id"]["channel_id"]

        if msg_type == "group":
            last = db.messages.find_one(
                {"type": "group", "group_id": cid}, sort=[("created_at", -1)]
            )
        else:
            last = db.messages.find_one(
                {"type": "channel", "channel_id": cid}, sort=[("created_at", -1)]
            )

        preview, last_at = "", None
        if last:
            preview = (last.get("content") or "")[:80] or "📎 File"
            last_at = last.get("created_at")

        convos.append({
            "type": msg_type,
            "conversation_id": cid,
            "display_name": cid,
            "last_message_preview": preview,
            "last_message_at": last_at,
        })

    # ── Private conversations ──
    seen: set = set()
    for row in db.messages.aggregate([
        {"$match": {
            "type": "private",
            "$or": [{"sender_id": user_id}, {"receiver_id": user_id}],
        }},
        {"$group": {
            "_id": {"sender_id": "$sender_id", "receiver_id": "$receiver_id"},
            "last_at": {"$max": "$created_at"},
        }},
        {"$sort": {"last_at": -1}},
    ]):
        other = (
            row["_id"]["receiver_id"]
            if row["_id"]["sender_id"] == user_id
            else row["_id"]["sender_id"]
        )
        if other in seen:
            continue
        seen.add(other)

        last = db.messages.find_one(
            {
                "type": "private",
                "$or": [
                    {"sender_id": user_id, "receiver_id": other},
                    {"sender_id": other, "receiver_id": user_id},
                ],
            },
            sort=[("created_at", -1)],
        )

        preview, last_at = "", None
        if last:
            preview = (last.get("content") or "")[:80] or "📎 File"
            last_at = last.get("created_at")

        convos.append({
            "type": "private",
            "conversation_id": other,
            "display_name": other,
            "last_message_preview": preview,
            "last_message_at": last_at,
        })

    return convos
