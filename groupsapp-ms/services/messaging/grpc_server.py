import os
import sys
import asyncio
import threading
from concurrent import futures
from datetime import timezone

import django
import grpc
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from google.protobuf import timestamp_pb2

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "messaging_service.settings")
django.setup()

sys.path.insert(0, os.path.dirname(__file__))
from generated import messaging_pb2, messaging_pb2_grpc, common_pb2

import repository as repo


def _ts(dt):
    ts = timestamp_pb2.Timestamp()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    ts.FromDatetime(dt)
    return ts


def _msg_to_proto(m):
    """Convert a MongoDB dict to a gRPC Message."""
    msg = messaging_pb2.Message(
        id=str(m["_id"]),
        sender_id=m.get("sender_id", ""),
        sender_username=m.get("sender_username", ""),
        type=m.get("type", ""),
        group_id=m.get("group_id", ""),
        channel_id=m.get("channel_id", ""),
        receiver_id=m.get("receiver_id", ""),
        content=m.get("content", ""),
        message_type=m.get("message_type", "text"),
        file_url=m.get("file_url", ""),
    )
    if m.get("created_at"):
        msg.created_at.CopyFrom(_ts(m["created_at"]))
    return msg


class MessagingServicer(messaging_pb2_grpc.MessagingServiceServicer):
    def Healthcheck(self, request, context):
        ts = timestamp_pb2.Timestamp()
        ts.GetCurrentTime()
        return common_pb2.HealthcheckResponse(
            service="messaging", status="OK", checked_at=ts
        )

    def PushDirectMessage(self, request, context):
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{request.user_id}",
            {"type": "push_notification", "payload_json": request.payload_json},
        )
        return common_pb2.Empty()

    def GetMessageHistory(self, request, context):
        limit = request.limit if request.limit > 0 else 50

        if request.group_id:
            rows = repo.get_group_history_sync(request.group_id, limit)
        elif request.channel_id:
            rows = repo.get_channel_history_sync(request.channel_id, limit)
        elif request.private_with_user_id:
            rows = repo.get_private_history_sync(
                request.requesting_user_id,
                request.private_with_user_id,
                limit,
            )
        else:
            return messaging_pb2.MessageHistoryResponse()

        return messaging_pb2.MessageHistoryResponse(
            messages=[_msg_to_proto(m) for m in reversed(rows)],
            next_cursor="",
        )

    def ListConversations(self, request, context):
        convos_raw = repo.list_conversations_sync(request.user_id)
        convos = []
        for row in convos_raw:
            c = messaging_pb2.ConversationSummary(
                type=row["type"],
                conversation_id=row["conversation_id"],
                display_name=row["display_name"],
                last_message_preview=row.get("last_message_preview", ""),
            )
            if row.get("last_message_at"):
                c.last_message_at.CopyFrom(_ts(row["last_message_at"]))
            convos.append(c)
        return messaging_pb2.ConversationsResponse(conversations=convos)


def serve_grpc():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    messaging_pb2_grpc.add_MessagingServiceServicer_to_server(MessagingServicer(), server)
    server.add_insecure_port("0.0.0.0:50054")
    server.start()
    print("Messaging gRPC server listening on :50054", flush=True)
    server.wait_for_termination()


if __name__ == "__main__":
    from db import ensure_indexes

    # Ensure MongoDB indexes before starting (sync — PyMongo)
    ensure_indexes()

    grpc_thread = threading.Thread(target=serve_grpc, daemon=True)
    grpc_thread.start()

    from daphne.cli import CommandLineInterface
    print("Messaging Daphne starting on :8001", flush=True)
    CommandLineInterface().run(
        ["-b", "0.0.0.0", "-p", "8001", "messaging_service.asgi:application"]
    )
