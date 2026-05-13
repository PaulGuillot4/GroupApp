import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from channels.testing import WebsocketCommunicator
from messaging_service.asgi import application


@pytest.mark.asyncio
async def test_connect_without_token_rejects():
    communicator = WebsocketCommunicator(application, "/ws/chat/")
    connected, code = await communicator.connect()
    assert not connected
    await communicator.disconnect()


@pytest.mark.asyncio
async def test_connect_with_valid_token_accepts():
    mock_identity = MagicMock()
    mock_identity.user_id = "user-ws-1"
    mock_identity.username = "wsuser"

    mock_auth_stub = MagicMock()
    mock_auth_stub.ValidateToken.return_value = mock_identity

    mock_groups_stub = MagicMock()
    mock_groups_stub.ListUserGroups.return_value = MagicMock(groups=[])

    with patch("chat.consumers.get_auth_stub", return_value=mock_auth_stub), \
         patch("chat.consumers.get_groups_stub", return_value=mock_groups_stub):
        communicator = WebsocketCommunicator(application, "/ws/chat/?token=valid.jwt.token")
        connected, _ = await communicator.connect()
        assert connected
        await communicator.disconnect()
