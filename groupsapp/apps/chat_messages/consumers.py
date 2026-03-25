"""
ChatConsumer – handles all real-time messaging over WebSockets.

Events handled (client → server):
  join_room, send_message, typing, mark_as_read, set_presence

Events emitted (server → client):
  new_message, message_delivered, message_read, user_typing, presence_update
"""

import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from apps.chat_messages.models import Message, MessageStatus
from apps.groups.models import Channel, Group, GroupMember

User = get_user_model()


# ------------------------------------------------------------------
# Sync DB helpers (run inside database_sync_to_async)
# ------------------------------------------------------------------

@database_sync_to_async
def _is_group_member(user, group_id):
    return GroupMember.objects.filter(group_id=group_id, user=user).exists()


@database_sync_to_async
def _is_channel_member(user, channel_id):
    try:
        channel = Channel.objects.select_related("group").get(pk=channel_id)
    except Channel.DoesNotExist:
        return False
    return GroupMember.objects.filter(group=channel.group, user=user).exists()


@database_sync_to_async
def _get_channel_group_id(channel_id):
    """Return the group id that owns this channel."""
    try:
        return str(Channel.objects.get(pk=channel_id).group_id)
    except Channel.DoesNotExist:
        return None


@database_sync_to_async
def _share_common_group(user, other_user_id):
    my = set(GroupMember.objects.filter(user=user).values_list("group_id", flat=True))
    other = set(GroupMember.objects.filter(user_id=other_user_id).values_list("group_id", flat=True))
    return bool(my & other)


@database_sync_to_async
def _user_exists(user_id):
    return User.objects.filter(pk=user_id).exists()


@database_sync_to_async
def _create_message(sender, room_id, content, message_type, file_url, room_kind):
    """Create and return a Message + its serialized dict."""
    msg_data = {
        "sender": sender,
        "content": content,
        "message_type": message_type or "text",
        "file_url": file_url or "",
    }
    if room_kind == "group":
        msg_data["type"] = "group"
        msg_data["group_id"] = room_id
    elif room_kind == "channel":
        msg_data["type"] = "channel"
        msg_data["channel_id"] = room_id
    elif room_kind == "private":
        msg_data["type"] = "private"
        msg_data["receiver_id"] = room_id

    msg = Message.objects.create(**msg_data)

    # Create 'sent' status for the sender
    MessageStatus.objects.create(message=msg, user=sender, status="sent")

    return {
        "id": str(msg.id),
        "sender": {
            "id": sender.id,
            "username": sender.username,
            "avatar": sender.avatar.url if sender.avatar else None,
        },
        "type": msg.type,
        "group": str(msg.group_id) if msg.group_id else None,
        "channel": str(msg.channel_id) if msg.channel_id else None,
        "receiver": msg.receiver_id,
        "content": msg.content,
        "message_type": msg.message_type,
        "file_url": msg.file_url,
        "created_at": msg.created_at.isoformat(),
    }


@database_sync_to_async
def _mark_delivered(message_id, user):
    MessageStatus.objects.update_or_create(
        message_id=message_id,
        user=user,
        defaults={"status": "delivered"},
    )


@database_sync_to_async
def _mark_read(message_id, user):
    updated = MessageStatus.objects.filter(
        message_id=message_id, user=user
    ).update(status="read")
    if not updated:
        try:
            MessageStatus.objects.create(
                message_id=message_id, user=user, status="read"
            )
        except Exception:
            pass
    msg = Message.objects.filter(pk=message_id).first()
    if msg:
        if msg.type == "group":
            return msg.sender_id, f"group_{msg.group_id}"
        elif msg.type == "channel":
            return msg.sender_id, f"channel_{msg.channel_id}"
        elif msg.type == "private":
            return msg.sender_id, _private_room_name(msg.sender_id, msg.receiver_id)
    return None, None


@database_sync_to_async
def _mark_previous_delivered(room_name, user):
    """Mark all undelivered messages in a room as delivered for this user."""
    parts = room_name.split("_", 1)
    kind = parts[0]
    room_id = parts[1] if len(parts) > 1 else None

    if kind == "group":
        msgs = Message.objects.filter(type="group", group_id=room_id).exclude(sender=user)
    elif kind == "channel":
        msgs = Message.objects.filter(type="channel", channel_id=room_id).exclude(sender=user)
    elif kind == "private":
        ids = room_id.split("_") if room_id else []
        other_id = ids[1] if str(ids[0]) == str(user.id) else ids[0]
        msgs = Message.objects.filter(
            type="private", sender_id=other_id, receiver=user
        )
    else:
        return

    for msg in msgs:
        MessageStatus.objects.get_or_create(
            message=msg, user=user,
            defaults={"status": "delivered"},
        )


@database_sync_to_async
def _update_last_seen(user):
    User.objects.filter(pk=user.pk).update(last_seen=timezone.now())


@database_sync_to_async
def _get_user_rooms(user):
    """Return all channel-group names the user should be in."""
    rooms = []
    memberships = GroupMember.objects.filter(user=user).select_related("group")
    for m in memberships:
        rooms.append(f"group_{m.group_id}")
        for ch in Channel.objects.filter(group=m.group):
            rooms.append(f"channel_{ch.id}")
    return rooms


# ------------------------------------------------------------------
# Room name helpers
# ------------------------------------------------------------------

def _private_room_name(uid1, uid2):
    """Canonical private room – IDs sorted."""
    a, b = sorted([str(uid1), str(uid2)])
    return f"private_{a}_{b}"


def _parse_room(room_id_raw):
    """
    Parse a roomId from the client into (kind, room_name).
    Expected formats from client:
      "group_<uuid>"    → ("group",   "group_<uuid>")
      "channel_<uuid>"  → ("channel", "channel_<uuid>")
      "private_<id>"    → ("private", determined later)
    """
    if room_id_raw.startswith("group_"):
        return "group", room_id_raw
    elif room_id_raw.startswith("channel_"):
        return "channel", room_id_raw
    elif room_id_raw.startswith("private_"):
        return "private", room_id_raw
    return None, None


# ===================================================================
# ChatConsumer
# ===================================================================

class ChatConsumer(AsyncWebsocketConsumer):

    async def send_json(self, content):
        await self.send(text_data=json.dumps(content, default=str))

    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close(code=4001)
            return

        self.user = user
        self.rooms = set()
        
        # Join personal room for private notifications
        self.personal_room = f"user_{self.user.id}"
        await self.channel_layer.group_add(self.personal_room, self.channel_name)
        
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'personal_room'):
            await self.channel_layer.group_discard(self.personal_room, self.channel_name)

        # Leave all rooms
        for room in list(self.rooms):
            await self.channel_layer.group_discard(room, self.channel_name)
            await self.channel_layer.group_send(room, {
                "type": "presence.update",
                "userId": self.user.id,
                "status": "offline",
                "lastSeen": timezone.now().isoformat(),
            })

        await _update_last_seen(self.user)
        self.rooms.clear()

    async def receive(self, text_data=None, bytes_data=None):
        try:
            content = json.loads(text_data)
        except (json.JSONDecodeError, TypeError):
            await self.send_json({"error": "Invalid JSON."})
            return
        action = content.get("action")
        handler = {
            "join_room": self._handle_join_room,
            "send_message": self._handle_send_message,
            "typing": self._handle_typing,
            "mark_as_read": self._handle_mark_as_read,
            "set_presence": self._handle_set_presence,
        }.get(action)

        if handler is None:
            await self.send_json({"error": "Unknown action."})
            return

        await handler(content)

    # ------------------------------------------------------------------
    # Event handlers (client → server)
    # ------------------------------------------------------------------

    async def _handle_join_room(self, data):
        room_id_raw = data.get("roomId", "")
        kind, room_name = _parse_room(room_id_raw)

        if kind is None:
            await self.send_json({"error": "Invalid roomId format."})
            return

        # Validate access
        has_access = False
        if kind == "group":
            gid = room_name.replace("group_", "", 1)
            has_access = await _is_group_member(self.user, gid)
        elif kind == "channel":
            cid = room_name.replace("channel_", "", 1)
            has_access = await _is_channel_member(self.user, cid)
        elif kind == "private":
            # private_<uid1>_<uid2>
            parts = room_name.split("_")
            if len(parts) == 3:
                other_id = parts[2] if str(parts[1]) == str(self.user.id) else parts[1]
                has_access = await _user_exists(other_id)

        if not has_access:
            await self.close(code=4003)
            return

        # Join the channel group
        await self.channel_layer.group_add(room_name, self.channel_name)
        self.rooms.add(room_name)

        # Mark previous messages as delivered
        await _mark_previous_delivered(room_name, self.user)

        # Notify presence
        await self.channel_layer.group_send(room_name, {
            "type": "presence.update",
            "userId": self.user.id,
            "status": "online",
            "lastSeen": None,
        })

    async def _handle_send_message(self, data):
        room_id_raw = data.get("roomId", "")
        content = data.get("content", "")
        message_type = data.get("messageType", "text")
        file_url = data.get("fileUrl")

        kind, room_name = _parse_room(room_id_raw)
        if kind is None or room_name not in self.rooms:
            await self.send_json({"error": "You are not in this room or invalid roomId."})
            return

        # Determine the DB foreign key target
        if kind == "group":
            db_room_id = room_name.replace("group_", "", 1)
        elif kind == "channel":
            db_room_id = room_name.replace("channel_", "", 1)
        elif kind == "private":
            parts = room_name.split("_")
            db_room_id = parts[2] if str(parts[1]) == str(self.user.id) else parts[1]
        else:
            return

        msg_data = await _create_message(
            sender=self.user,
            room_id=db_room_id,
            content=content,
            message_type=message_type,
            file_url=file_url,
            room_kind=kind,
        )

        # Broadcast new_message to the room
        await self.channel_layer.group_send(room_name, {
            "type": "chat.new_message",
            "message": msg_data,
        })
        
        # If private, also broadcast to both users' personal rooms so they get notifications / live updates
        # even if they do not have the private room actively opened.
        if kind == "private":
            await self.channel_layer.group_send(f"user_{db_room_id}", {
                "type": "chat.new_message",
                "message": msg_data,
            })
            await self.channel_layer.group_send(f"user_{self.user.id}", {
                "type": "chat.new_message",
                "message": msg_data,
            })

    async def _handle_typing(self, data):
        room_id_raw = data.get("roomId", "")
        kind, room_name = _parse_room(room_id_raw)
        if room_name and room_name in self.rooms:
            await self.channel_layer.group_send(room_name, {
                "type": "chat.user_typing",
                "userId": self.user.id,
                "roomId": room_id_raw,
                "exclude": self.channel_name,
            })

    async def _handle_mark_as_read(self, data):
        message_id = data.get("messageId")
        if not message_id:
            await self.send_json({"error": "messageId is required."})
            return

        sender_id, room_name = await _mark_read(message_id, self.user)
        if not sender_id:
            await self.send_json({"error": "Message not found"})
            return

        payload = {
            "type": "chat.message_read",
            "messageId": str(message_id),
            "userId": self.user.id,
        }
        
        # Notify the sender specifically
        await self.channel_layer.group_send(f"user_{sender_id}", payload)
        
        # In a group setting, also notify the room
        if room_name:
            await self.channel_layer.group_send(room_name, payload)

    async def _handle_set_presence(self, data):
        presence = data.get("status", "online")
        last_seen = None
        if presence == "offline":
            await _update_last_seen(self.user)
            last_seen = timezone.now().isoformat()

        for room_name in self.rooms:
            await self.channel_layer.group_send(room_name, {
                "type": "presence.update",
                "userId": self.user.id,
                "status": presence,
                "lastSeen": last_seen,
            })

    # ------------------------------------------------------------------
    # Channel-layer event handlers (server → client)
    # ------------------------------------------------------------------

    async def chat_new_message(self, event):
        """Broadcast new_message to connected clients."""
        msg = event["message"]
        await self.send_json({
            "event": "new_message",
            "message": msg,
        })
        # Mark as delivered for everyone except sender
        if msg["sender"]["id"] != self.user.id:
            await _mark_delivered(msg["id"], self.user)
            # Notify the sender that this user received it
            sender_id = msg["sender"]["id"]
            await self.channel_layer.group_send(f"user_{sender_id}", {
                "type": "chat.message_delivered",
                "messageId": msg["id"],
                "userId": self.user.id
            })

    async def chat_message_delivered(self, event):
        await self.send_json({
            "event": "message_delivered",
            "messageId": event["messageId"],
            "userId": event["userId"],
        })

    async def chat_message_read(self, event):
        await self.send_json({
            "event": "message_read",
            "messageId": event["messageId"],
            "userId": event["userId"],
        })

    async def chat_user_typing(self, event):
        # Don't send typing to the user who is typing
        if event.get("exclude") == self.channel_name:
            return
        await self.send_json({
            "event": "user_typing",
            "userId": event["userId"],
            "roomId": event["roomId"],
        })

    async def presence_update(self, event):
        await self.send_json({
            "event": "presence_update",
            "userId": event["userId"],
            "status": event["status"],
            "lastSeen": event.get("lastSeen"),
        })
