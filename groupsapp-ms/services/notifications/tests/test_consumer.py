import pytest
import json
from unittest.mock import MagicMock, patch


@pytest.mark.asyncio
async def test_handle_messages_sent_private_calls_push():
    from src.main import handle_messages_sent
    event = json.dumps({
        "message_id": "msg-1",
        "sender_id": "user-a",
        "type": "private",
        "receiver_id": "user-b",
        "content_preview": "Hello",
    }).encode()

    mock_stub = MagicMock()
    mock_stub.PushDirectMessage.return_value = MagicMock()

    with patch("src.main.get_messaging_stub", return_value=mock_stub):
        await handle_messages_sent(event)

    mock_stub.PushDirectMessage.assert_called_once()
    call_arg = mock_stub.PushDirectMessage.call_args[0][0]
    assert call_arg.user_id == "user-b"


@pytest.mark.asyncio
async def test_handle_messages_sent_group_does_not_push():
    """Group messages without members list → no push (ListMembers returns empty)."""
    from src.main import handle_messages_sent
    event = json.dumps({
        "message_id": "msg-2",
        "sender_id": "user-a",
        "type": "group",
        "group_id": "grp-1",
        "content_preview": "Hi group",
    }).encode()

    mock_msg_stub = MagicMock()
    mock_groups_stub = MagicMock()
    # ListMembers returns only the sender → no push needed
    mock_member = MagicMock()
    mock_member.user_id = "user-a"
    mock_groups_stub.ListMembers.return_value = MagicMock(members=[mock_member])

    with patch("src.main.get_messaging_stub", return_value=mock_msg_stub), \
         patch("src.main.get_groups_stub", return_value=mock_groups_stub):
        await handle_messages_sent(event)

    # Sender is excluded → no push calls
    mock_msg_stub.PushDirectMessage.assert_not_called()


@pytest.mark.asyncio
async def test_handle_messages_sent_group_pushes_to_members():
    """Group messages should push to all members except the sender."""
    from src.main import handle_messages_sent
    event = json.dumps({
        "message_id": "msg-3",
        "sender_id": "user-a",
        "type": "group",
        "group_id": "grp-2",
        "content_preview": "Hello group!",
    }).encode()

    mock_msg_stub = MagicMock()
    mock_msg_stub.PushDirectMessage.return_value = MagicMock()

    # Group has 3 members: sender + 2 others
    members = []
    for uid in ["user-a", "user-b", "user-c"]:
        m = MagicMock()
        m.user_id = uid
        members.append(m)
    mock_groups_stub = MagicMock()
    mock_groups_stub.ListMembers.return_value = MagicMock(members=members)

    with patch("src.main.get_messaging_stub", return_value=mock_msg_stub), \
         patch("src.main.get_groups_stub", return_value=mock_groups_stub):
        await handle_messages_sent(event)

    # Should push to user-b and user-c, NOT user-a (sender)
    assert mock_msg_stub.PushDirectMessage.call_count == 2
    pushed_user_ids = [
        call[0][0].user_id
        for call in mock_msg_stub.PushDirectMessage.call_args_list
    ]
    assert "user-b" in pushed_user_ids
    assert "user-c" in pushed_user_ids
    assert "user-a" not in pushed_user_ids


@pytest.mark.asyncio
async def test_handle_messages_sent_private_without_receiver_does_not_push():
    """Private messages without receiver_id should be ignored."""
    from src.main import handle_messages_sent
    event = json.dumps({
        "message_id": "msg-4",
        "sender_id": "user-a",
        "type": "private",
        "receiver_id": "",
        "content_preview": "No receiver",
    }).encode()

    mock_stub = MagicMock()
    with patch("src.main.get_messaging_stub", return_value=mock_stub):
        await handle_messages_sent(event)

    mock_stub.PushDirectMessage.assert_not_called()


@pytest.mark.asyncio
async def test_handle_presence_changed_updates_last_seen():
    from src.main import handle_presence_changed
    from datetime import datetime, timezone
    event = json.dumps({
        "user_id": "user-x",
        "status": "online",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }).encode()

    mock_stub = MagicMock()
    mock_stub.UpdateLastSeen.return_value = MagicMock()

    with patch("src.main.get_users_stub", return_value=mock_stub):
        await handle_presence_changed(event)

    mock_stub.UpdateLastSeen.assert_called_once()


@pytest.mark.asyncio
async def test_handle_messages_read_does_not_crash():
    """messages.read handler should log without errors."""
    from src.main import handle_messages_read
    event = json.dumps({
        "message_id": "msg-read-1",
        "user_id": "user-reader",
        "timestamp": "2026-04-26T12:00:00+00:00",
    }).encode()
    # Should not raise
    await handle_messages_read(event)
