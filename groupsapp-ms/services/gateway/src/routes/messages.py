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
        "group": m.group_id,
        "channel": m.channel_id,
        "receiver": m.receiver_id,
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
    stub = get_messaging_stub()
    try:
        resp = stub.GetMessageHistory(messaging_pb2.GetMessageHistoryRequest(
            group_id=group_id,
            channel_id=channel_id,
            private_with_user_id=private_with,
            requesting_user_id=current_user["user_id"],
            limit=limit,
        ))
        return {
            "messages": [_msg_to_dict(m) for m in resp.messages],
            "next_cursor": resp.next_cursor,
        }
    except grpc.RpcError:
        raise HTTPException(status_code=503, detail="Messaging service unavailable")


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
