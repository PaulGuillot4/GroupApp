import asyncio
import json
from datetime import datetime, timezone

from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async

from clients import get_auth_stub, get_groups_stub
from chat.kafka_producer import send_message_event


def _validate_token_sync(token: str):
    from generated import auth_pb2
    return get_auth_stub().ValidateToken(auth_pb2.ValidateTokenRequest(token=token))


def _list_user_groups_sync(user_id: str):
    from generated import groups_pb2
    return get_groups_stub().ListUserGroups(
        groups_pb2.ListUserGroupsRequest(user_id=user_id)
    ).groups


def _verify_membership_sync(user_id: str, group_id: str) -> bool:
    from generated import groups_pb2
    return get_groups_stub().VerifyMembership(
        groups_pb2.MembershipRequest(user_id=user_id, group_id=group_id)
    ).is_member


def _private_room(a: str, b: str) -> str:
    """Canonical sorted private-room key."""
    return "private_" + "_".join(sorted([a, b]))


class ChatConsumer(AsyncWebsocketConsumer):

    # ── Lifecycle ────────────────────────────────────────────────────

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

        self.user_id: str = identity.user_id
        self.username: str = identity.username
        self.joined_rooms: set[str] = set()

        await self.accept()

        await self._join(f"user_{self.user_id}")

        try:
            groups = await asyncio.to_thread(_list_user_groups_sync, self.user_id)
            for g in groups:
                await self._join(f"group_{g.id}")
        except Exception:
            pass

        await send_message_event("presence.changed", {
            "user_id": self.user_id,
            "status": "online",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def disconnect(self, close_code):
        if not hasattr(self, "user_id"):
            return

        for room in list(self.joined_rooms):
            await self.channel_layer.group_discard(room, self.channel_name)
            await self.channel_layer.group_send(room, {
                "type": "presence_update",
                "user_id": self.user_id,
                "status": "offline",
                "last_seen": datetime.now(timezone.utc).isoformat(),
            })

        await send_message_event("presence.changed", {
            "user_id": self.user_id,
            "status": "offline",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except ValueError:
            return

        action = data.get("action")
        if action == "join_room":
            await self._handle_join_room(data)
        elif action == "send_message":
            await self._handle_send_message(data)
        elif action == "typing":
            await self._handle_typing(data)
        elif action == "mark_as_read":
            await self._handle_mark_as_read(data)
        elif action == "set_presence":
            await self._handle_set_presence(data)

    # ── Action Handlers ──────────────────────────────────────────────

    async def _handle_join_room(self, data):
        from chat.models import Message, MessageStatus

        room_id: str = data.get("roomId", "")
        if not room_id:
            return

        # Validate access for group rooms
        if room_id.startswith("group_"):
            group_id = room_id[6:]
            try:
                ok = await asyncio.to_thread(_verify_membership_sync, self.user_id, group_id)
                if not ok:
                    await self.send(json.dumps({"event": "error", "detail": "Not a member"}))
                    return
            except Exception:
                return

        await self._join(room_id)

        # Mark unread messages in this room as delivered, notify senders
        try:
            unread = await self._unread_messages_for_room(room_id)
            for msg in unread:
                await sync_to_async(MessageStatus.objects.update_or_create)(
                    message_id=msg.id,
                    user_id=self.user_id,
                    defaults={"status": "delivered"},
                )
                await self.channel_layer.group_send(f"user_{msg.sender_id}", {
                    "type": "chat_message_delivered",
                    "message_id": str(msg.id),
                })
        except Exception:
            pass

    async def _handle_send_message(self, data):
        from chat.models import Message

        room_id: str = data.get("roomId", "")
        content: str = data.get("content", "")
        message_type: str = data.get("messageType", "text")
        file_url: str = data.get("fileUrl", "")

        group_id = channel_id = receiver_id = ""
        msg_type = ""

        if room_id.startswith("group_"):
            group_id = room_id[6:]
            msg_type = "group"
            try:
                ok = await asyncio.to_thread(_verify_membership_sync, self.user_id, group_id)
                if not ok:
                    await self.send(json.dumps({"event": "error", "detail": "Not a member"}))
                    return
            except Exception:
                return
        elif room_id.startswith("channel_"):
            channel_id = room_id[8:]
            msg_type = "channel"
        elif room_id.startswith("private_"):
            msg_type = "private"
            rest = room_id[8:]
            id1, id2 = rest.split("_", 1)
            receiver_id = id1 if id2 == self.user_id else id2
        else:
            return

        msg = await sync_to_async(Message.objects.create)(
            sender_id=self.user_id,
            sender_username=self.username,
            type=msg_type,
            group_id=group_id,
            channel_id=channel_id,
            receiver_id=receiver_id,
            content=content,
            message_type=message_type,
            file_url=file_url,
        )

        payload = {
            "id": str(msg.id),
            "type": msg_type,
            "group": group_id,
            "channel": channel_id,
            "receiver": receiver_id,
            "sender": {"id": self.user_id, "username": self.username},
            "content": content,
            "message_type": message_type,
            "file_url": file_url,
            "created_at": msg.created_at.isoformat(),
            "status": "sent",
        }
        event = {"type": "chat_new_message", "message": payload}

        await self.channel_layer.group_send(room_id, event)

        if msg_type == "private":
            canonical = _private_room(self.user_id, receiver_id)
            if canonical != room_id:
                await self.channel_layer.group_send(canonical, event)
            # Always notify receiver's personal room (covers when receiver hasn't opened the chat)
            await self.channel_layer.group_send(f"user_{receiver_id}", event)

        await send_message_event("messages.sent", {
            "message_id": str(msg.id),
            "sender_id": self.user_id,
            "type": msg_type,
            "group_id": group_id,
            "channel_id": channel_id,
            "receiver_id": receiver_id,
            "content_preview": content[:100],
        })

    async def _handle_typing(self, data):
        room_id: str = data.get("roomId", "")
        if not room_id:
            return
        await self.channel_layer.group_send(room_id, {
            "type": "chat_user_typing",
            "user_id": self.user_id,
            "room_id": room_id,
            "exclude_channel": self.channel_name,
        })

    async def _handle_mark_as_read(self, data):
        from chat.models import Message, MessageStatus

        message_id: str = data.get("messageId", "")
        if not message_id:
            return

        try:
            await sync_to_async(MessageStatus.objects.update_or_create)(
                message_id=message_id,
                user_id=self.user_id,
                defaults={"status": "read"},
            )
        except Exception:
            pass

        await send_message_event("messages.read", {
            "message_id": message_id,
            "user_id": self.user_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        try:
            sender_id = await sync_to_async(
                Message.objects.filter(id=message_id).values_list("sender_id", flat=True).first
            )()
            if sender_id and sender_id != self.user_id:
                await self.channel_layer.group_send(f"user_{sender_id}", {
                    "type": "chat_message_read",
                    "message_id": message_id,
                })
        except Exception:
            pass

    async def _handle_set_presence(self, data):
        status = data.get("status", "online")
        for room in self.joined_rooms:
            await self.channel_layer.group_send(room, {
                "type": "presence_update",
                "user_id": self.user_id,
                "status": status,
                "last_seen": datetime.now(timezone.utc).isoformat(),
            })

    # ── Channel Layer → Browser ──────────────────────────────────────

    async def chat_new_message(self, event):
        await self.send(text_data=json.dumps({
            "event": "new_message",
            "message": event["message"],
        }))

    async def chat_message_delivered(self, event):
        await self.send(text_data=json.dumps({
            "event": "message_delivered",
            "messageId": event["message_id"],
        }))

    async def chat_message_read(self, event):
        await self.send(text_data=json.dumps({
            "event": "message_read",
            "messageId": event["message_id"],
        }))

    async def chat_user_typing(self, event):
        if event.get("exclude_channel") == self.channel_name:
            return
        await self.send(text_data=json.dumps({
            "event": "user_typing",
            "userId": event["user_id"],
            "roomId": event["room_id"],
        }))

    async def presence_update(self, event):
        await self.send(text_data=json.dumps({
            "event": "presence_update",
            "userId": event["user_id"],
            "status": event["status"],
        }))

    async def push_notification(self, event):
        await self.send(text_data=event["payload_json"])

    # ── Helpers ──────────────────────────────────────────────────────

    async def _join(self, room: str):
        await self.channel_layer.group_add(room, self.channel_name)
        self.joined_rooms.add(room)

    async def _unread_messages_for_room(self, room_id: str):
        from chat.models import Message
        from django.db.models import Q

        if room_id.startswith("group_"):
            group_id = room_id[6:]
            return await sync_to_async(list)(
                Message.objects.filter(type="group", group_id=group_id)
                .exclude(sender_id=self.user_id)
                .exclude(statuses__user_id=self.user_id,
                         statuses__status__in=["delivered", "read"])
            )
        elif room_id.startswith("channel_"):
            channel_id = room_id[8:]
            return await sync_to_async(list)(
                Message.objects.filter(type="channel", channel_id=channel_id)
                .exclude(sender_id=self.user_id)
                .exclude(statuses__user_id=self.user_id,
                         statuses__status__in=["delivered", "read"])
            )
        elif room_id.startswith("private_"):
            rest = room_id[8:]
            id1, id2 = rest.split("_", 1)
            other = id1 if id2 == self.user_id else id2
            return await sync_to_async(list)(
                Message.objects.filter(type="private", sender_id=other, receiver_id=self.user_id)
                .exclude(statuses__user_id=self.user_id,
                         statuses__status__in=["delivered", "read"])
            )
        return []

    @staticmethod
    def _parse_token(query_string: str) -> str:
        for part in query_string.split("&"):
            if part.startswith("token="):
                return part[len("token="):]
        return ""
