import os
import sys
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


def _ts(dt):
    ts = timestamp_pb2.Timestamp()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    ts.FromDatetime(dt)
    return ts


def _msg_to_proto(m):
    msg = messaging_pb2.Message(
        id=str(m.id),
        sender_id=m.sender_id,
        sender_username=m.sender_username,
        type=m.type,
        group_id=m.group_id,
        channel_id=m.channel_id,
        receiver_id=m.receiver_id,
        content=m.content,
        message_type=m.message_type,
        file_url=m.file_url,
    )
    msg.created_at.CopyFrom(_ts(m.created_at))
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
        from chat.models import Message
        from django.db.models import Q

        limit = request.limit if request.limit > 0 else 50

        if request.group_id:
            qs = Message.objects.filter(type="group", group_id=request.group_id)
        elif request.channel_id:
            qs = Message.objects.filter(type="channel", channel_id=request.channel_id)
        elif request.private_with_user_id:
            uid = request.requesting_user_id
            other = request.private_with_user_id
            qs = Message.objects.filter(type="private").filter(
                Q(sender_id=uid, receiver_id=other)
                | Q(sender_id=other, receiver_id=uid)
            )
        else:
            return messaging_pb2.MessageHistoryResponse()

        rows = list(qs.order_by("-created_at")[:limit])
        return messaging_pb2.MessageHistoryResponse(
            messages=[_msg_to_proto(m) for m in reversed(rows)],
            next_cursor="",
        )

    def ListConversations(self, request, context):
        from chat.models import Message
        from django.db.models import Q, Max

        uid = request.user_id
        convos = []

        # Groups and channels where user participated
        for row in (
            Message.objects.filter(type__in=["group", "channel"], sender_id=uid)
            .values("type", "group_id", "channel_id")
            .annotate(last_at=Max("created_at"))
            .order_by("-last_at")
        ):
            msg_type = row["type"]
            if msg_type == "group":
                cid = row["group_id"]
                last = (
                    Message.objects.filter(type="group", group_id=cid)
                    .order_by("-created_at")
                    .first()
                )
            else:  # channel
                cid = row["channel_id"]
                last = (
                    Message.objects.filter(type="channel", channel_id=cid)
                    .order_by("-created_at")
                    .first()
                )
            preview = ""
            ts = None
            if last:
                preview = last.content[:80] if last.content else "📎 File"
                ts = _ts(last.created_at)
            c = messaging_pb2.ConversationSummary(
                type=msg_type,
                conversation_id=cid,
                display_name=cid,
                last_message_preview=preview,
            )
            if ts:
                c.last_message_at.CopyFrom(ts)
            convos.append(c)

        # Private conversations
        seen: set = set()
        for row in (
            Message.objects.filter(type="private")
            .filter(Q(sender_id=uid) | Q(receiver_id=uid))
            .values("sender_id", "receiver_id")
            .annotate(last_at=Max("created_at"))
            .order_by("-last_at")
        ):
            other = row["receiver_id"] if row["sender_id"] == uid else row["sender_id"]
            if other in seen:
                continue
            seen.add(other)
            last = (
                Message.objects.filter(type="private")
                .filter(
                    Q(sender_id=uid, receiver_id=other)
                    | Q(sender_id=other, receiver_id=uid)
                )
                .order_by("-created_at")
                .first()
            )
            preview = ""
            ts = None
            if last:
                preview = last.content[:80] if last.content else "📎 File"
                ts = _ts(last.created_at)
            c = messaging_pb2.ConversationSummary(
                type="private",
                conversation_id=other,
                display_name=other,
                last_message_preview=preview,
            )
            if ts:
                c.last_message_at.CopyFrom(ts)
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
    import django.core.management
    django.core.management.call_command("migrate", "--noinput", verbosity=0)

    grpc_thread = threading.Thread(target=serve_grpc, daemon=True)
    grpc_thread.start()

    from daphne.cli import CommandLineInterface
    print("Messaging Daphne starting on :8001", flush=True)
    CommandLineInterface().run(
        ["-b", "0.0.0.0", "-p", "8001", "messaging_service.asgi:application"]
    )
