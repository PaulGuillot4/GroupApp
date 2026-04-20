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
    from src.main import handle_messages_sent
    event = json.dumps({
        "message_id": "msg-2",
        "sender_id": "user-a",
        "type": "group",
        "group_id": "grp-1",
        "content_preview": "Hi group",
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
