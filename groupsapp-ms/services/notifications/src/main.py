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


async def handle_messages_sent(value: bytes):
    data = json.loads(value)
    if data.get("type") != "private":
        return
    receiver_id = data.get("receiver_id", "")
    if not receiver_id:
        return
    payload = json.dumps({
        "event": "new_message",
        "message_id": data.get("message_id"),
        "sender_id": data.get("sender_id"),
        "content_preview": data.get("content_preview", ""),
    })
    stub = get_messaging_stub()
    from generated import messaging_pb2
    stub.PushDirectMessage(
        messaging_pb2.PushDirectMessageRequest(user_id=receiver_id, payload_json=payload)
    )
    print(f"[notifications] pushed to {receiver_id}", flush=True)


async def handle_messages_read(value: bytes):
    data = json.loads(value)
    print(f"[notifications] message read: {data.get('message_id')}", flush=True)


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
    print(f"[notifications] updated last_seen for {user_id}", flush=True)


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
