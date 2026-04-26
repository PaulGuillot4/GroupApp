import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from channels.testing import WebsocketCommunicator
from messaging_service.asgi import application


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_mark_read_updates_status():
    """Sending a 'read' message should create a MessageStatus and publish to Kafka."""
    from chat.models import Message, MessageStatus
    from asgiref.sync import sync_to_async

    # Create a message to mark as read
    msg = await sync_to_async(Message.objects.create)(
        sender_id="u-sender",
        type="private",
        receiver_id="u-reader",
        content="Hello!",
        message_type="text",
    )

    mock_identity = MagicMock()
    mock_identity.user_id = "u-reader"
    mock_identity.username = "reader"

    mock_auth_stub = MagicMock()
    mock_auth_stub.ValidateToken.return_value = mock_identity

    mock_groups_stub = MagicMock()
    mock_groups_stub.ListUserGroups.return_value = MagicMock(groups=[])

    mock_kafka = AsyncMock()

    with patch("chat.consumers.get_auth_stub", return_value=mock_auth_stub), \
         patch("chat.consumers.get_groups_stub", return_value=mock_groups_stub), \
         patch("chat.consumers.send_message_event", mock_kafka):
        communicator = WebsocketCommunicator(application, "/ws/chat/?token=tok")
        connected, _ = await communicator.connect()
        assert connected

        # Send mark-as-read
        await communicator.send_json_to({
            "type": "read",
            "message_id": str(msg.id),
        })

        # Give it a moment to process
        import asyncio
        await asyncio.sleep(0.3)

        # Check MessageStatus was created
        status_count = await sync_to_async(
            MessageStatus.objects.filter(message_id=msg.id, user_id="u-reader").count
        )()
        assert status_count == 1

        # Check Kafka events: should have presence.changed (connect) + messages.read
        kafka_calls = [call[0] for call in mock_kafka.call_args_list]
        topics = [call[0] for call in kafka_calls]
        assert "presence.changed" in topics
        assert "messages.read" in topics

        await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_presence_changed_on_connect_disconnect():
    """Connecting and disconnecting should publish presence.changed events."""
    mock_identity = MagicMock()
    mock_identity.user_id = "u-presence"
    mock_identity.username = "presenceuser"

    mock_auth_stub = MagicMock()
    mock_auth_stub.ValidateToken.return_value = mock_identity

    mock_groups_stub = MagicMock()
    mock_groups_stub.ListUserGroups.return_value = MagicMock(groups=[])

    mock_kafka = AsyncMock()

    with patch("chat.consumers.get_auth_stub", return_value=mock_auth_stub), \
         patch("chat.consumers.get_groups_stub", return_value=mock_groups_stub), \
         patch("chat.consumers.send_message_event", mock_kafka):
        communicator = WebsocketCommunicator(application, "/ws/chat/?token=tok")
        connected, _ = await communicator.connect()
        assert connected

        # Verify online event was published
        assert mock_kafka.call_count >= 1
        first_call = mock_kafka.call_args_list[0]
        assert first_call[0][0] == "presence.changed"
        assert first_call[0][1]["status"] == "online"
        assert first_call[0][1]["user_id"] == "u-presence"

        await communicator.disconnect()

        # Verify offline event was published
        offline_calls = [
            c for c in mock_kafka.call_args_list
            if c[0][0] == "presence.changed" and c[0][1].get("status") == "offline"
        ]
        assert len(offline_calls) >= 1


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_send_message_with_file_url():
    """Sending a message with file_url should persist it."""
    from chat.models import Message
    from asgiref.sync import sync_to_async

    mock_identity = MagicMock()
    mock_identity.user_id = "u-file-sender"
    mock_identity.username = "filesender"

    mock_auth_stub = MagicMock()
    mock_auth_stub.ValidateToken.return_value = mock_identity

    mock_groups_stub = MagicMock()
    mock_groups_stub.ListUserGroups.return_value = MagicMock(groups=[])

    with patch("chat.consumers.get_auth_stub", return_value=mock_auth_stub), \
         patch("chat.consumers.get_groups_stub", return_value=mock_groups_stub), \
         patch("chat.consumers.send_message_event", new_callable=AsyncMock):
        communicator = WebsocketCommunicator(application, "/ws/chat/?token=tok")
        connected, _ = await communicator.connect()
        assert connected

        await communicator.send_json_to({
            "type": "message",
            "content": "Check this file",
            "receiver_id": "u-receiver",
            "message_type": "file",
            "file_url": "http://files:8002/files/test-file.png",
        })
        resp = await communicator.receive_json_from()
        assert resp["message_type"] == "file"
        assert resp["file_url"] == "http://files:8002/files/test-file.png"

        # Verify persisted
        msg = await sync_to_async(
            Message.objects.filter(sender_id="u-file-sender").first
        )()
        assert msg is not None
        assert msg.file_url == "http://files:8002/files/test-file.png"
        assert msg.message_type == "file"

        await communicator.disconnect()
