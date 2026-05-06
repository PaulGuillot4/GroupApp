# Frontend Gateway Integration – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve the complete frontend (HTML/JS/CSS) from the FastAPI Gateway on `localhost:8000`, proxy WebSocket traffic to the messaging service, and rewrite the ChatConsumer with full action/event parity so that the browser app works identically to the monolith without `groupsapp/` running.

**Architecture:** Gateway mounts Jinja2 templates and StaticFiles, proxies `/ws/chat/` bidirectionally to `messaging:8001`, normalises all REST responses to match the field shapes expected by the existing `chat.js`, and proxies media downloads via `/media/{path}`. The messaging service ChatConsumer is fully rewritten to handle the `action`-keyed messages sent by `chat.js` and to emit `event`-keyed frames back.

**Tech Stack:** FastAPI, Jinja2, Python `websockets` library, Django Channels, Redis channel layer, Kafka, gRPC (auth / users / groups / messaging), pytest + httpx TestClient.

---

### Task 1: Add `sender_username` to `messaging.proto` + Message model

**Files:**
- Modify: `groupsapp-ms/proto/messaging.proto`
- Modify: `groupsapp-ms/services/messaging/chat/models.py`
- Create migration (Django management command)

**Why:** The history endpoint must return a nested `sender: { id, username }` object. Storing the username alongside the message avoids a per-row gRPC call to the users service during history queries.

- [ ] **Step 1: Add `sender_username` field (tag 11) to Message proto**

Edit `groupsapp-ms/proto/messaging.proto` — replace the `Message` block:

```protobuf
message Message {
  string id = 1;
  string sender_id = 2;
  string type = 3;
  string group_id = 4;
  string channel_id = 5;
  string receiver_id = 6;
  string content = 7;
  string message_type = 8;
  string file_url = 9;
  google.protobuf.Timestamp created_at = 10;
  string sender_username = 11;
}
```

The gRPC code for both `messaging` and `gateway` is regenerated from this proto at Docker build time via each service's Dockerfile (`grpc_tools.protoc`). No manual regeneration step is needed — the rebuild in Task 11 picks it up.

- [ ] **Step 2: Add `sender_username` to the Message Django model**

Replace the `Message` class in `groupsapp-ms/services/messaging/chat/models.py`:

```python
import uuid
from django.db import models


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sender_id = models.CharField(max_length=36)
    sender_username = models.CharField(max_length=150, blank=True, default="")
    type = models.CharField(max_length=20)
    group_id = models.CharField(max_length=36, blank=True, default="")
    channel_id = models.CharField(max_length=36, blank=True, default="")
    receiver_id = models.CharField(max_length=36, blank=True, default="")
    content = models.TextField(blank=True, default="")
    message_type = models.CharField(max_length=20, default="text")
    file_url = models.CharField(max_length=512, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "chat"
        ordering = ["-created_at"]


class MessageStatus(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="statuses")
    user_id = models.CharField(max_length=36)
    status = models.CharField(max_length=20, default="sent")  # sent | delivered | read
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "chat"
        unique_together = [("message", "user_id")]
```

- [ ] **Step 3: Create the migration (run inside the messaging container or locally with Django set up)**

```bash
cd groupsapp-ms
docker compose run --rm messaging python manage.py makemigrations chat --name add_sender_username
```

Expected output: `Migrations for 'chat': chat/migrations/00XX_add_sender_username.py`

- [ ] **Step 4: Verify migration applies**

```bash
docker compose run --rm messaging python manage.py migrate --noinput
```

Expected: `Applying chat.00XX_add_sender_username... OK`

- [ ] **Step 5: Commit**

```bash
git add groupsapp-ms/proto/messaging.proto \
        groupsapp-ms/services/messaging/chat/models.py \
        groupsapp-ms/services/messaging/chat/migrations/
git commit -m "feat(messaging): add sender_username to Message model and proto"
```

---

### Task 2: Fix `grpc_server.py` – populate `sender_username` + fix `ListConversations`

**Files:**
- Modify: `groupsapp-ms/services/messaging/grpc_server.py`

**Why:** `_msg_to_proto` must include the new field; `ListConversations` currently returns empty `last_message_preview`/`last_message_at`, making the sidebar useless.

- [ ] **Step 1: Update `_msg_to_proto` to include `sender_username`**

Replace the function in `grpc_server.py`:

```python
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
```

- [ ] **Step 2: Fix `ListConversations` to return real `last_message_preview` and `last_message_at`**

Replace the `ListConversations` method:

```python
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
        cid = row["group_id"] or row["channel_id"]
        last = (
            Message.objects.filter(type=row["type"], group_id=cid or None, channel_id=cid or None)
            .order_by("-created_at")
            .first()
        )
        preview = ""
        ts = None
        if last:
            preview = last.content[:80] if last.content else "📎 File"
            ts = _ts(last.created_at)
        c = messaging_pb2.ConversationSummary(
            type=row["type"],
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
```

Note: `display_name` is still the raw ID here. The Gateway enriches it with real names.

- [ ] **Step 3: Commit**

```bash
git add groupsapp-ms/services/messaging/grpc_server.py
git commit -m "fix(messaging): populate sender_username and last_message_preview in gRPC responses"
```

---

### Task 3: Rewrite `ChatConsumer` – full action/event parity

**Files:**
- Modify: `groupsapp-ms/services/messaging/chat/consumers.py`

**Why:** The current consumer handles `type`-keyed messages but `chat.js` sends `action`-keyed messages; private rooms use `user_<receiver_id>` instead of the canonical sorted form; emitted events use the wrong key (`type` instead of `event`); and `join_room`, `typing`, `set_presence` are entirely missing.

- [ ] **Step 1: Replace `consumers.py` completely**

```python
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
            rest = room_id[8:]
            id1, id2 = rest.split("_", 1)
            receiver_id = id1 if id2 == self.user_id else id2
            msg_type = "private"
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
            # Always notify receiver's personal room (covers the case where
            # receiver hasn't opened the chat yet and is not in the private room)
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
```

- [ ] **Step 2: Commit**

```bash
git add groupsapp-ms/services/messaging/chat/consumers.py
git commit -m "feat(messaging): full ChatConsumer rewrite with join_room, typing, mark_as_read, set_presence, canonical private rooms"
```

---

### Task 4: Gateway – add `jinja2`, `websockets`, `aiofiles` + update Dockerfile

**Files:**
- Modify: `groupsapp-ms/services/gateway/requirements.txt`
- Modify: `groupsapp-ms/services/gateway/Dockerfile`

- [ ] **Step 1: Update `requirements.txt`**

```
fastapi==0.111.*
uvicorn[standard]==0.30.*
grpcio==1.63.*
grpcio-tools==1.63.*
protobuf==5.27.*
pydantic==2.*
python-multipart==0.0.9
httpx==0.27.*
jinja2==3.1.*
websockets==12.*
aiofiles==23.*
pytest==8.*
pytest-mock==3.*
```

- [ ] **Step 2: Verify Dockerfile already covers templates/ and static/**

The current Dockerfile has:

```dockerfile
COPY services/gateway/ /app/
```

This copies everything under `services/gateway/` into `/app/`, including the `templates/` and `static/` subdirectories we will create in Task 5. No Dockerfile change is needed.

- [ ] **Step 3: Commit**

```bash
git add groupsapp-ms/services/gateway/requirements.txt
git commit -m "feat(gateway): add jinja2, websockets, aiofiles to requirements"
```

---

### Task 5: Copy and adapt templates + static files from monolith

**Files:**
- Create: `groupsapp-ms/services/gateway/templates/` (mirrored from `groupsapp/templates/`)
- Create: `groupsapp-ms/services/gateway/static/` (mirrored from `groupsapp/static/`)

- [ ] **Step 1: Copy templates**

```bash
cp -r groupsapp/templates/. groupsapp-ms/services/gateway/templates/
```

Resulting structure:
```
groupsapp-ms/services/gateway/templates/
├── base.html
├── auth/
│   ├── login.html
│   └── register.html
└── app/
    └── chat.html
```

- [ ] **Step 2: Adapt `chat.html` for Jinja2 (remove Django-specific tags)**

`groupsapp-ms/services/gateway/templates/app/chat.html` — make three changes:

1. Remove line 2: `{% load static %}`
2. Line 8: change `{% static 'css/chat.css' %}` → `/static/css/chat.css`
3. Line 203 (the `<script src=...>`): change `{% static 'js/chat.js' %}` → `/static/js/chat.js`

The result at lines 1–10:
```html
{% extends 'base.html' %}

{% block head %}
<!-- Material Symbols for icons -->
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined" rel="stylesheet" />
<!-- Chat-specific styles (extracted from inline) -->
<link rel="stylesheet" href="/static/css/chat.css">
{% endblock %}
```

And near the bottom where chat.js is loaded:
```html
<script src="/static/js/chat.js"></script>
```

- [ ] **Step 3: Adapt `auth/login.html` – fix `{% url %}` tag**

Replace `{% url 'frontend:register' %}` with `/auth/register/`:

```html
<a href="/auth/register/" class="text-[#00a884] hover:text-[#008f6f] font-semibold transition-colors">Register</a>
```

- [ ] **Step 4: Adapt `auth/register.html` – fix `{% url %}` tag**

Replace `{% url 'frontend:login' %}` with `/auth/login/`:

```html
<a href="/auth/login/" class="text-[#00a884] hover:text-[#008f6f] font-semibold transition-colors">Sign in</a>
```

`base.html` has no Django-specific tags — no changes needed.

- [ ] **Step 5: Copy static files**

```bash
mkdir -p groupsapp-ms/services/gateway/static/js
mkdir -p groupsapp-ms/services/gateway/static/css
cp groupsapp/static/js/chat.js groupsapp-ms/services/gateway/static/js/
cp groupsapp/static/css/chat.css groupsapp-ms/services/gateway/static/css/
cp groupsapp/static/css/app.css  groupsapp-ms/services/gateway/static/css/
```

- [ ] **Step 6: Commit**

```bash
git add groupsapp-ms/services/gateway/templates/ groupsapp-ms/services/gateway/static/
git commit -m "feat(gateway): copy and adapt monolith templates and static assets"
```

---

### Task 6: Gateway – `routes/frontend.py` (4 HTML routes)

**Files:**
- Create: `groupsapp-ms/services/gateway/src/routes/frontend.py`

- [ ] **Step 1: Write failing tests**

Create `groupsapp-ms/services/gateway/tests/test_frontend.py`:

```python
from fastapi.testclient import TestClient
import pytest


def test_root_redirects_to_login(client):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"] == "/auth/login/"


def test_login_page_returns_html(client):
    resp = client.get("/auth/login/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_register_page_returns_html(client):
    resp = client.get("/auth/register/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_app_page_returns_html(client):
    resp = client.get("/app/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
```

Add a `conftest.py` at `groupsapp-ms/services/gateway/tests/conftest.py` if it doesn't exist:

```python
import pytest
from fastapi.testclient import TestClient
from src.main import app


@pytest.fixture
def client():
    return TestClient(app)
```

- [ ] **Step 2: Run tests (expect failure — route doesn't exist yet)**

```bash
cd groupsapp-ms/services/gateway
pytest tests/test_frontend.py -v
```

Expected: FAILED with 404.

- [ ] **Step 3: Create `routes/frontend.py`**

```python
import os
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["frontend"])

_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(_base, "templates"))


@router.get("/")
def root():
    return RedirectResponse(url="/auth/login/", status_code=307)


@router.get("/auth/login/")
def login_page(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request})


@router.get("/auth/register/")
def register_page(request: Request):
    return templates.TemplateResponse("auth/register.html", {"request": request})


@router.get("/app/")
def chat_page(request: Request):
    return templates.TemplateResponse("app/chat.html", {"request": request})
```

Note: `_base` resolves to `services/gateway/src/` → `services/gateway/`, so `templates/` is found correctly.

- [ ] **Step 4: Include router in `main.py` (temporary, full wiring in Task 10)**

Add to `main.py` for tests to pass:

```python
from .routes.frontend import router as frontend_router
app.include_router(frontend_router)
```

- [ ] **Step 5: Run tests (expect pass)**

```bash
pytest tests/test_frontend.py -v
```

Expected: 4 PASSED.

- [ ] **Step 6: Commit**

```bash
git add groupsapp-ms/services/gateway/src/routes/frontend.py \
        groupsapp-ms/services/gateway/tests/
git commit -m "feat(gateway): add HTML routes for login, register, and chat pages"
```

---

### Task 7: Gateway – `routes/ws_proxy.py` (bidirectional WebSocket proxy)

**Files:**
- Create: `groupsapp-ms/services/gateway/src/routes/ws_proxy.py`

**Why:** The Gateway must accept `/ws/chat/?token=JWT` from the browser and forward all frames to `messaging:8001/ws/chat/?token=JWT`, then relay responses back. The JWT is forwarded untouched — the ChatConsumer validates it.

- [ ] **Step 1: Create `routes/ws_proxy.py`**

```python
import asyncio
import os

import websockets
import websockets.exceptions
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])

MESSAGING_WS = os.getenv("MESSAGING_WS", "ws://localhost:8001")


@router.websocket("/ws/chat/")
async def ws_proxy(websocket: WebSocket):
    query = websocket.scope.get("query_string", b"").decode()
    upstream_url = f"{MESSAGING_WS}/ws/chat/?{query}"

    await websocket.accept()

    try:
        async with websockets.connect(upstream_url) as upstream:

            async def _browser_to_upstream():
                try:
                    while True:
                        text = await websocket.receive_text()
                        await upstream.send(text)
                except (WebSocketDisconnect, Exception):
                    await upstream.close()

            async def _upstream_to_browser():
                try:
                    async for message in upstream:
                        await websocket.send_text(message)
                except Exception:
                    pass

            done, pending = await asyncio.wait(
                [
                    asyncio.ensure_future(_browser_to_upstream()),
                    asyncio.ensure_future(_upstream_to_browser()),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()

    except websockets.exceptions.InvalidURI:
        await websocket.close(code=1011)
    except Exception:
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
```

- [ ] **Step 2: Commit**

```bash
git add groupsapp-ms/services/gateway/src/routes/ws_proxy.py
git commit -m "feat(gateway): add bidirectional WebSocket proxy /ws/chat/ → messaging:8001"
```

---

### Task 8: Gateway – REST aliases and response normalisation

#### 8a – `routes/users.py`: add `id` alias to user responses

**Files:**
- Modify: `groupsapp-ms/services/gateway/src/routes/users.py`

**Why:** `chat.js` reads `user.id` (from `/api/users/me/`) and `u.id` (from search results). The MS currently returns only `user_id`.

- [ ] **Step 1: Write failing test**

Add to `groupsapp-ms/services/gateway/tests/test_users.py` (create if needed):

```python
from unittest.mock import MagicMock


def test_get_me_includes_id_field(client, mocker):
    mock_user = MagicMock()
    mock_user.id = "user-uuid-1"
    mock_user.username = "alice"
    mock_user.email = "alice@test.com"
    mocker.patch("src.routes.users.get_auth_stub").return_value.GetUserById.return_value = mock_user
    mocker.patch("src.routes.users.get_current_user", return_value={"user_id": "user-uuid-1"})

    resp = client.get("/api/users/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "user-uuid-1"
    assert data["user_id"] == "user-uuid-1"
```

- [ ] **Step 2: Update `UserResponse` and `UserSummaryResponse` to include `id`**

In `groupsapp-ms/services/gateway/src/routes/users.py`:

```python
class UserResponse(BaseModel):
    user_id: str
    id: str          # alias – chat.js uses response.id
    username: str
    email: str


class UserSummaryResponse(BaseModel):
    user_id: str
    id: str          # alias – chat.js uses u.id in search results
    username: str
    avatar_url: str
```

Update `get_me` to set both fields:

```python
@router.get("/me", response_model=UserResponse)
def get_me(current_user: dict = Depends(get_current_user)):
    stub = get_auth_stub()
    try:
        user = stub.GetUserById(auth_pb2.GetUserByIdRequest(user_id=current_user["user_id"]))
        return UserResponse(
            user_id=user.id, id=user.id, username=user.username, email=user.email
        )
    except grpc.RpcError as exc:
        if exc.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail="User not found")
        raise HTTPException(status_code=500, detail="Auth service error")
```

Update `search_users` to set both fields:

```python
return [
    UserSummaryResponse(user_id=u.user_id, id=u.user_id, username=u.username, avatar_url=u.avatar_url)
    for u in resp.users
]
```

- [ ] **Step 3: Run test (expect pass)**

```bash
pytest tests/test_users.py -v
```

- [ ] **Step 4: Commit**

```bash
git add groupsapp-ms/services/gateway/src/routes/users.py
git commit -m "fix(gateway): add id alias to user responses for chat.js compatibility"
```

---

#### 8b – `routes/groups.py`: `GET /api/groups/` alias + members with usernames

**Files:**
- Modify: `groupsapp-ms/services/gateway/src/routes/groups.py`

**Why:** `chat.js` posts to `POST /api/groups/` (handled by existing route) and the spec requires a `GET /api/groups/` alias. The `GET /{group_id}/members` response must return `{ user: { id, username }, role }` — `chat.js` accesses `m.user.id` and `m.user.username`.

- [ ] **Step 1: Add `GET /api/groups/` alias at the top of the router (before the `/{group_id}` catch-all)**

The alias must be declared **before** `GET /{group_id}` to avoid route conflict. Insert after `list_my_groups`:

```python
@router.get("/", include_in_schema=False)
def list_my_groups_root(current_user: dict = Depends(get_current_user)):
    """GET /api/groups/ alias for chat.js compatibility."""
    return list_my_groups(current_user=current_user)
```

- [ ] **Step 2: Enrich `list_members` to include usernames**

Add imports to groups.py:

```python
from generated import users_pb2
from ..clients import get_users_stub
```

Replace `list_members`:

```python
@router.get("/{group_id}/members")
def list_members(group_id: str, current_user: dict = Depends(get_current_user)):
    groups_stub = get_groups_stub()
    users_stub_inst = get_users_stub()
    try:
        resp = groups_stub.ListMembers(groups_pb2.GetGroupRequest(group_id=group_id))
        result = []
        for m in resp.members:
            try:
                profile = users_stub_inst.GetProfile(
                    users_pb2.GetProfileRequest(user_id=m.user_id)
                )
                username = profile.username
            except Exception:
                username = m.user_id
            result.append({"user": {"id": m.user_id, "username": username}, "role": m.role})
        return result
    except grpc.RpcError as e:
        _handle_rpc_error(e)
```

- [ ] **Step 3: Commit**

```bash
git add groupsapp-ms/services/gateway/src/routes/groups.py
git commit -m "feat(gateway): add GET /api/groups/ alias and enrich members with usernames"
```

---

#### 8c – `routes/messages.py`: history aliases + full response normalisation

**Files:**
- Modify: `groupsapp-ms/services/gateway/src/routes/messages.py`

**Why:** `chat.js` calls `/api/messages/group/<id>/`, `/api/messages/channel/<id>/`, `/api/messages/private/<id>/`, and `/api/messages/conversations/`. The response format must be `{ results: [...], next: ... }` with messages using `sender: { id, username }`, `group`, `channel`, `receiver` field names (not `_id` suffixed). Conversations must become `{ kind, id, name, last_message }`.

- [ ] **Step 1: Write failing tests**

Create `groupsapp-ms/services/gateway/tests/test_messages.py`:

```python
from unittest.mock import MagicMock, patch
from datetime import datetime


def _make_msg(sender_id="u1", sender_username="alice", msg_type="group",
              group_id="g1", channel_id="", receiver_id=""):
    m = MagicMock()
    m.id = "msg-1"
    m.sender_id = sender_id
    m.sender_username = sender_username
    m.type = msg_type
    m.group_id = group_id
    m.channel_id = channel_id
    m.receiver_id = receiver_id
    m.content = "hello"
    m.message_type = "text"
    m.file_url = ""
    m.created_at.ToDatetime.return_value = datetime(2024, 1, 1)
    return m


def test_group_history_alias_normalized(client, mocker):
    stub = mocker.patch("src.routes.messages.get_messaging_stub").return_value
    stub.GetMessageHistory.return_value.messages = [_make_msg()]
    stub.GetMessageHistory.return_value.next_cursor = ""
    mocker.patch("src.routes.messages.get_current_user", return_value={"user_id": "u1"})

    resp = client.get("/api/messages/group/g1/")
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    msg = data["results"][0]
    assert msg["sender"]["id"] == "u1"
    assert msg["sender"]["username"] == "alice"
    assert msg["group"] == "g1"
    assert "group_id" not in msg
    assert "next" in data


def test_private_history_alias(client, mocker):
    stub = mocker.patch("src.routes.messages.get_messaging_stub").return_value
    stub.GetMessageHistory.return_value.messages = []
    stub.GetMessageHistory.return_value.next_cursor = ""
    mocker.patch("src.routes.messages.get_current_user", return_value={"user_id": "u1"})

    resp = client.get("/api/messages/private/u2/")
    assert resp.status_code == 200
    assert stub.GetMessageHistory.call_args.kwargs["private_with_user_id"] == "u2" \
        or stub.GetMessageHistory.call_args[0][0].private_with_user_id == "u2"


def test_conversations_normalized(client, mocker):
    conv = MagicMock()
    conv.type = "private"
    conv.conversation_id = "u2"
    conv.display_name = "u2"
    conv.last_message_preview = "hi"
    conv.last_message_at.ToDatetime.return_value = datetime(2024, 1, 1)

    mocker.patch("src.routes.messages.get_messaging_stub").return_value \
        .ListConversations.return_value.conversations = [conv]
    profile = MagicMock()
    profile.username = "Bob"
    mocker.patch("src.routes.messages.get_users_stub").return_value \
        .GetProfile.return_value = profile
    mocker.patch("src.routes.messages.get_current_user", return_value={"user_id": "u1"})

    resp = client.get("/api/messages/conversations/")
    assert resp.status_code == 200
    c = resp.json()[0]
    assert c["kind"] == "private"
    assert c["name"] == "Bob"
    assert c["last_message"]["content"] == "hi"
```

- [ ] **Step 2: Run tests (expect failure)**

```bash
pytest tests/test_messages.py -v
```

- [ ] **Step 3: Rewrite `routes/messages.py`**

```python
import grpc
from fastapi import APIRouter, Depends, HTTPException

from generated import messaging_pb2, users_pb2, groups_pb2
from ..clients import get_messaging_stub, get_users_stub, get_groups_stub
from ..deps import get_current_user

router = APIRouter(prefix="/api/messages", tags=["messages"])


def _msg_to_dict(m) -> dict:
    """Normalize a gRPC Message to the shape chat.js expects."""
    try:
        created_at = m.created_at.ToDatetime().isoformat()
    except Exception:
        created_at = ""
    return {
        "id": m.id,
        "type": m.type,
        "group": m.group_id,        # chat.js uses msg.group, not msg.group_id
        "channel": m.channel_id,    # chat.js uses msg.channel
        "receiver": m.receiver_id,  # chat.js uses msg.receiver
        "sender": {
            "id": m.sender_id,
            "username": m.sender_username,
        },
        "content": m.content,
        "message_type": m.message_type,
        "file_url": m.file_url,
        "created_at": created_at,
        "status": "sent",
    }


def _get_history(group_id="", channel_id="", private_with="",
                 requesting_user_id="", limit=50) -> dict:
    stub = get_messaging_stub()
    try:
        resp = stub.GetMessageHistory(messaging_pb2.GetMessageHistoryRequest(
            group_id=group_id,
            channel_id=channel_id,
            private_with_user_id=private_with,
            requesting_user_id=requesting_user_id,
            limit=limit,
        ))
        return {
            "results": [_msg_to_dict(m) for m in resp.messages],
            "next": resp.next_cursor if resp.next_cursor else None,
        }
    except grpc.RpcError:
        raise HTTPException(status_code=503, detail="Messaging service unavailable")


# ── Original route (kept for backward compat) ───────────────────────

@router.get("/history")
def get_history(
    group_id: str = "",
    channel_id: str = "",
    private_with: str = "",
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
):
    return _get_history(group_id=group_id, channel_id=channel_id,
                        private_with=private_with,
                        requesting_user_id=current_user["user_id"],
                        limit=limit)


# ── chat.js aliases ──────────────────────────────────────────────────

@router.get("/group/{group_id}/")
@router.get("/group/{group_id}")
def get_group_history(
    group_id: str,
    page: int = 1,
    current_user: dict = Depends(get_current_user),
):
    return _get_history(group_id=group_id,
                        requesting_user_id=current_user["user_id"])


@router.get("/channel/{channel_id}/")
@router.get("/channel/{channel_id}")
def get_channel_history(
    channel_id: str,
    page: int = 1,
    current_user: dict = Depends(get_current_user),
):
    return _get_history(channel_id=channel_id,
                        requesting_user_id=current_user["user_id"])


@router.get("/private/{other_user_id}/")
@router.get("/private/{other_user_id}")
def get_private_history(
    other_user_id: str,
    page: int = 1,
    current_user: dict = Depends(get_current_user),
):
    return _get_history(private_with=other_user_id,
                        requesting_user_id=current_user["user_id"])


@router.get("/conversations/")
@router.get("/conversations")
def list_conversations(current_user: dict = Depends(get_current_user)):
    """Normalize ListConversations to the {kind, id, name, last_message} shape chat.js expects."""
    try:
        resp = get_messaging_stub().ListConversations(
            messaging_pb2.ListConversationsRequest(user_id=current_user["user_id"])
        )
    except grpc.RpcError:
        raise HTTPException(status_code=503, detail="Messaging service unavailable")

    result = []
    for c in resp.conversations:
        name = c.display_name

        # Resolve human-readable display name
        if c.type == "private":
            try:
                profile = get_users_stub().GetProfile(
                    users_pb2.GetProfileRequest(user_id=c.conversation_id)
                )
                name = profile.username
            except Exception:
                name = c.conversation_id
        elif c.type in ("group", "channel"):
            try:
                group = get_groups_stub().GetGroup(
                    groups_pb2.GetGroupRequest(group_id=c.conversation_id)
                )
                name = group.name
            except Exception:
                name = c.conversation_id

        # Build last_message object
        last_message = None
        if c.last_message_preview:
            try:
                created_at = c.last_message_at.ToDatetime().isoformat()
            except Exception:
                created_at = ""
            last_message = {
                "message_type": "text",
                "content": c.last_message_preview,
                "created_at": created_at,
            }

        result.append({
            "kind": c.type,
            "id": c.conversation_id,
            "name": name,
            "last_message": last_message,
        })

    return result
```

- [ ] **Step 4: Run tests (expect pass)**

```bash
pytest tests/test_messages.py -v
```

Expected: All passing.

- [ ] **Step 5: Commit**

```bash
git add groupsapp-ms/services/gateway/src/routes/messages.py
git commit -m "feat(gateway): add history aliases and normalize message/conversation format for chat.js"
```

---

#### 8d – `routes/files.py`: add `/media/{path}` proxy

**Files:**
- Modify: `groupsapp-ms/services/gateway/src/routes/files.py`

**Why:** Uploaded files are stored at `files:8002`. After docker-compose changes, only the Gateway is exposed. The browser must fetch media via `http://localhost:8000/media/<uuid>.ext`.

- [ ] **Step 1: Add `media_router` to `files.py`**

Add after the existing routes in `files.py`:

```python
from fastapi.responses import Response

media_router = APIRouter(tags=["media"])


@media_router.get("/media/{path:path}")
async def proxy_media(path: str):
    """Proxy /media/{path} → files:8002/files/{path}."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{FILES_HTTP_URL}/files/{path}", timeout=15.0
            )
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                media_type=resp.headers.get("content-type", "application/octet-stream"),
            )
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Files service unavailable")
```

Export `media_router` at the module level (it's already accessible as `files.media_router`).

- [ ] **Step 2: Commit**

```bash
git add groupsapp-ms/services/gateway/src/routes/files.py
git commit -m "feat(gateway): add /media/{path} proxy to files service"
```

---

### Task 9: Gateway – update `main.py` to wire everything together

**Files:**
- Modify: `groupsapp-ms/services/gateway/src/main.py`

- [ ] **Step 1: Write test for static file serving**

Add to `tests/test_main.py` (create if needed):

```python
def test_static_js_is_served(client):
    resp = client.get("/static/js/chat.js")
    assert resp.status_code == 200
    assert "javascript" in resp.headers.get("content-type", "")


def test_health_still_works(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "OK"
```

- [ ] **Step 2: Replace `main.py`**

```python
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .routes.auth import router as auth_router
from .routes.users import router as users_router
from .routes.groups import router as groups_router
from .routes.messages import router as messages_router
from .routes.files import router as files_router, media_router
from .routes.frontend import router as frontend_router
from .routes.ws_proxy import router as ws_router

app = FastAPI(title="GroupsApp Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve /static/* from services/gateway/static/
_static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../static")
app.mount("/static", StaticFiles(directory=_static_dir), name="static")

# Route order matters: frontend and ws before api routes
app.include_router(frontend_router)
app.include_router(ws_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(groups_router)
app.include_router(messages_router)
app.include_router(files_router)
app.include_router(media_router)


@app.get("/health")
def health():
    return {"service": "gateway", "status": "OK"}
```

- [ ] **Step 3: Run all gateway tests**

```bash
cd groupsapp-ms/services/gateway
pytest tests/ -v
```

Expected: All passing.

- [ ] **Step 4: Commit**

```bash
git add groupsapp-ms/services/gateway/src/main.py
git commit -m "feat(gateway): mount StaticFiles, include frontend and ws_proxy routers"
```

---

### Task 10: docker-compose – expose only Gateway; add env vars

**Files:**
- Modify: `groupsapp-ms/docker-compose.yml`

- [ ] **Step 1: Remove external ports from `messaging` and `files`; add env vars to `gateway`**

In `groupsapp-ms/docker-compose.yml`, apply these changes:

**`messaging` service** — remove `"8001:8001"` from `ports` (keep `50054:50054` for gRPC):

```yaml
messaging:
  ports:
    - "50054:50054"
    # 8001 is now internal only — gateway proxies /ws/chat/
```

**`files` service** — remove `"8002:8002"` from `ports`; update `FILES_BASE_URL`:

```yaml
files:
  environment:
    ...
    FILES_BASE_URL: http://localhost:8000/media   # URLs the browser will use
  ports:
    - "50055:50055"
    # 8002 is now internal only — gateway proxies /media/
```

**`gateway` service** — add the two new env vars:

```yaml
gateway:
  environment:
    AUTH_GRPC: auth:50051
    USERS_GRPC: users:50052
    GROUPS_GRPC: groups:50053
    MESSAGING_GRPC: messaging:50054
    FILES_GRPC: files:50055
    USERS_HTTP: http://users:8003
    FILES_HTTP: http://files:8002
    MESSAGING_WS: ws://messaging:8001   # NEW — for WS proxy
    FILES_BASE_URL: http://localhost:8000/media  # NEW — for upload URL prefix
```

- [ ] **Step 2: Build and bring up the full stack**

```bash
cd groupsapp-ms
docker compose down -v
docker compose build
docker compose up -d
```

Watch for all services to reach `healthy` / `running`:

```bash
docker compose ps
```

Expected: `gms_gateway`, `gms_messaging`, `gms_files`, `gms_auth`, `gms_users`, `gms_groups`, `gms_postgres`, `gms_kafka`, `gms_zookeeper`, `gms_notifications` — all `Up`.

- [ ] **Step 3: End-to-end smoke tests (manual)**

1. `curl http://localhost:8000/health` → `{"service":"gateway","status":"OK"}`
2. Open `http://localhost:8000` in browser → redirects to `/auth/login/` → login page renders
3. Open `http://localhost:8000/auth/register/` → register page renders
4. Register two users (user A and user B)
5. Log in as user A → redirected to `/app/` → chat UI loads
6. `http://localhost:8000/static/js/chat.js` → returns the JS file
7. Open a second browser window / incognito tab, log in as user B
8. In user A's window: search for user B → appears in search results
9. Click user B → opens private chat room
10. In user B's window: click user A in search (or conversation sidebar)
11. User A types and sends "hello" → user B receives it in real time
12. User B replies → user A sees it with typing indicator first
13. Tick updates: single ✓ (sent) → double ✓ gray (delivered) → double ✓ blue (read)
14. Upload an image in user A's window → appears in chat; image loads from `/media/...`

- [ ] **Step 4: Commit**

```bash
git add groupsapp-ms/docker-compose.yml
git commit -m "feat(compose): route all frontend traffic through gateway; remove external ports from messaging and files"
```

---

## Definition of Done

All of the following must pass before the feature is considered complete:

- [ ] `docker compose up -d` in `groupsapp-ms/` starts without errors
- [ ] `http://localhost:8000` shows the login page
- [ ] Register → Login flow works and redirects to `/app/`
- [ ] Two users can exchange real-time messages in a group chat
- [ ] Two users can exchange real-time messages in a private chat
- [ ] Typing indicator appears when the other user is typing
- [ ] Message tick advances: sent (✓) → delivered (✓✓ gray) → read (✓✓ blue)
- [ ] Image upload works and the image loads from `http://localhost:8000/media/...`
- [ ] Conversation sidebar shows correct display names (not raw UUIDs)
- [ ] `groupsapp/` Django monolith is **not** running during any of the above tests
