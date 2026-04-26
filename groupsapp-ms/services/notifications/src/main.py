import asyncio
import json
import os
from datetime import datetime, timezone

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
TOPICS = ["messages.sent", "messages.read", "presence.changed"]


def get_messaging_stub():
    from src.clients import get_messaging_stub as _get
    return _get()


def get_users_stub():
    from src.clients import get_users_stub as _get
    return _get()


def get_groups_stub():
    from src.clients import get_groups_stub as _get
    return _get()


def _list_group_members(group_id: str) -> list[str]:
    """Return list of user_ids that are members of the given group."""
    from generated import groups_pb2
    stub = get_groups_stub()
    try:
        resp = stub.ListMembers(groups_pb2.GetGroupRequest(group_id=group_id))
        return [m.user_id for m in resp.members]
    except Exception as exc:
        print(f"[notifications] ListMembers failed for {group_id}: {exc}", flush=True)
        return []


async def handle_messages_sent(value: bytes):
    data = json.loads(value)
    msg_type = data.get("type", "")
    sender_id = data.get("sender_id", "")

    if msg_type == "private":
        # Push notification to the receiver
        receiver_id = data.get("receiver_id", "")
        if not receiver_id:
            return
        payload = json.dumps({
            "event": "new_message",
            "message_id": data.get("message_id"),
            "sender_id": sender_id,
            "content_preview": data.get("content_preview", ""),
            "type": "private",
        })
        stub = get_messaging_stub()
        from generated import messaging_pb2
        stub.PushDirectMessage(
            messaging_pb2.PushDirectMessageRequest(user_id=receiver_id, payload_json=payload)
        )
        print(f"[notifications] pushed private notification to {receiver_id}", flush=True)

    elif msg_type in ("group", "channel"):
        # Push notification to all group/channel members except the sender
        target_id = data.get("group_id") or data.get("channel_id", "")
        if not target_id:
            return
        members = await asyncio.to_thread(_list_group_members, target_id)
        stub = get_messaging_stub()
        from generated import messaging_pb2
        payload_data = {
            "event": "new_message",
            "message_id": data.get("message_id"),
            "sender_id": sender_id,
            "content_preview": data.get("content_preview", ""),
            "type": msg_type,
            "group_id": target_id,
        }
        pushed_count = 0
        for member_id in members:
            if member_id == sender_id:
                continue
            try:
                stub.PushDirectMessage(
                    messaging_pb2.PushDirectMessageRequest(
                        user_id=member_id,
                        payload_json=json.dumps(payload_data),
                    )
                )
                pushed_count += 1
            except Exception as exc:
                print(f"[notifications] push to {member_id} failed: {exc}", flush=True)
        print(
            f"[notifications] pushed {msg_type} notification to {pushed_count} members "
            f"in {target_id}",
            flush=True,
        )


async def handle_messages_read(value: bytes):
    data = json.loads(value)
    print(
        f"[notifications] message {data.get('message_id')} read by {data.get('user_id')}",
        flush=True,
    )


async def handle_presence_changed(value: bytes):
    data = json.loads(value)
    user_id = data.get("user_id", "")
    timestamp_str = data.get("timestamp", "")
    if not user_id or not timestamp_str:
        return
    try:
        dt = datetime.fromisoformat(timestamp_str)
    except ValueError:
        dt = datetime.now(timezone.utc)
    stub = get_users_stub()
    from generated import users_pb2
    from google.protobuf.timestamp_pb2 import Timestamp
    ts = Timestamp()
    ts.FromDatetime(dt)
    stub.UpdateLastSeen(users_pb2.UpdateLastSeenRequest(user_id=user_id, timestamp=ts))
    print(f"[notifications] updated last_seen for {user_id} ({data.get('status')})", flush=True)


_HANDLERS = {
    "messages.sent": handle_messages_sent,
    "messages.read": handle_messages_read,
    "presence.changed": handle_presence_changed,
}


async def consume():
    from aiokafka import AIOKafkaConsumer

    await asyncio.sleep(15)  # let Kafka start
    consumer = AIOKafkaConsumer(
        *TOPICS,
        bootstrap_servers=KAFKA_BROKER,
        group_id="notifications-group",
        auto_offset_reset="latest",
    )
    await consumer.start()
    print(f"[notifications] consuming {TOPICS}", flush=True)
    try:
        async for msg in consumer:
            handler = _HANDLERS.get(msg.topic)
            if handler:
                try:
                    await handler(msg.value)
                except Exception as exc:
                    print(f"[notifications] handler error on {msg.topic}: {exc}", flush=True)
    finally:
        await consumer.stop()


if __name__ == "__main__":
    print("Notifications service starting", flush=True)
    asyncio.run(consume())
