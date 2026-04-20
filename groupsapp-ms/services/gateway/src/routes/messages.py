from fastapi import APIRouter, Depends, HTTPException
import grpc

from generated import messaging_pb2
from ..clients import get_messaging_stub
from ..deps import get_current_user

router = APIRouter(prefix="/api/messages", tags=["messages"])


def _conv_to_dict(c) -> dict:
    return {
        "type": c.type,
        "conversation_id": c.conversation_id,
        "display_name": c.display_name,
        "last_message_preview": c.last_message_preview,
    }


def _msg_to_dict(m) -> dict:
    return {
        "id": m.id,
        "sender_id": m.sender_id,
        "type": m.type,
        "group_id": m.group_id,
        "channel_id": m.channel_id,
        "receiver_id": m.receiver_id,
        "content": m.content,
        "message_type": m.message_type,
        "file_url": m.file_url,
    }


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


@router.get("/conversations")
def list_conversations(current_user: dict = Depends(get_current_user)):
    stub = get_messaging_stub()
    try:
        resp = stub.ListConversations(
            messaging_pb2.ListConversationsRequest(user_id=current_user["user_id"])
        )
        return [_conv_to_dict(c) for c in resp.conversations]
    except grpc.RpcError:
        raise HTTPException(status_code=503, detail="Messaging service unavailable")
