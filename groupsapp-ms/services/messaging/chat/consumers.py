import asyncio
import json

from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async

from clients import get_auth_stub, get_groups_stub
from chat.kafka_producer import send_message_event


def _validate_token_sync(token: str):
    from generated import auth_pb2
    stub = get_auth_stub()
    return stub.ValidateToken(auth_pb2.ValidateTokenRequest(token=token))


def _list_user_groups_sync(user_id: str):
    from generated import groups_pb2
    stub = get_groups_stub()
    resp = stub.ListUserGroups(groups_pb2.ListUserGroupsRequest(user_id=user_id))
    return resp.groups


def _verify_membership_sync(user_id: str, group_id: str):
    from generated import groups_pb2
    stub = get_groups_stub()
    info = stub.VerifyMembership(
        groups_pb2.MembershipRequest(user_id=user_id, group_id=group_id)
    )
    return info.is_member


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        query = self.scope.get("query_string", b"").decode()
        token = self._parse_token(query)
        if not token:
            await self.close(code=4001)
            return
        try:
            identity = await asyncio.to_thread(_validate_token_sync, token)
        except Exception:
            await self.close(code=4001)
            return

        self.user_id = identity.user_id
        self.username = identity.username
        await self.accept()

        await self.channel_layer.group_add(f"user_{self.user_id}", self.channel_name)

        try:
            groups = await asyncio.to_thread(_list_user_groups_sync, self.user_id)
            for g in groups:
                await self.channel_layer.group_add(f"group_{g.id}", self.channel_name)
        except Exception:
            pass

    async def disconnect(self, close_code):
        if hasattr(self, "user_id"):
            await self.channel_layer.group_discard(
                f"user_{self.user_id}", self.channel_name
            )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except ValueError:
            return
        if data.get("type") == "message":
            await self._handle_message(data)

    async def _handle_message(self, data):
        from chat.models import Message

        content = data.get("content", "")
        group_id = data.get("group_id", "")
        channel_id = data.get("channel_id", "")
        receiver_id = data.get("receiver_id", "")
        message_type = data.get("message_type", "text")

        if group_id:
            msg_type = "group"
            scope_group = f"group_{group_id}"
            try:
                is_member = await asyncio.to_thread(
                    _verify_membership_sync, self.user_id, group_id
                )
                if not is_member:
                    await self.send(json.dumps({"type": "error", "detail": "Not a member"}))
                    return
            except Exception:
                await self.send(json.dumps({"type": "error", "detail": "Membership check failed"}))
                return
        elif channel_id:
            msg_type = "channel"
            scope_group = f"group_{channel_id}"
        else:
            msg_type = "private"
            scope_group = f"user_{receiver_id}"

        msg = await sync_to_async(Message.objects.create)(
            sender_id=self.user_id,
            type=msg_type,
            group_id=group_id,
            channel_id=channel_id,
            receiver_id=receiver_id,
            content=content,
            message_type=message_type,
        )

        payload = {
            "type": "chat_message",
            "message": {
                "type": "message",
                "message_id": str(msg.id),
                "sender_id": self.user_id,
                "sender": self.username,
                "content": content,
                "message_type": message_type,
                "created_at": msg.created_at.isoformat(),
            },
        }
        await self.channel_layer.group_send(scope_group, payload)
        if msg_type == "private" and scope_group != f"user_{self.user_id}":
            await self.channel_layer.group_send(f"user_{self.user_id}", payload)

        await send_message_event("messages.sent", {
            "message_id": str(msg.id),
            "sender_id": self.user_id,
            "type": msg_type,
            "group_id": group_id,
            "channel_id": channel_id,
            "receiver_id": receiver_id,
            "content_preview": content[:100],
        })

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event["message"]))

    async def push_notification(self, event):
        await self.send(text_data=event["payload_json"])

    @staticmethod
    def _parse_token(query_string: str) -> str:
        for part in query_string.split("&"):
            if part.startswith("token="):
                return part[len("token="):]
        return ""
