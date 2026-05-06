from unittest.mock import MagicMock, patch
from datetime import datetime
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from src.main import app
    return TestClient(app, raise_server_exceptions=True)


def _valid_identity(user_id="u1"):
    identity = MagicMock()
    identity.user_id = user_id
    identity.username = "testuser"
    return identity


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


def test_group_history_alias_normalized(client):
    hist_mock = MagicMock()
    hist_mock.messages = [_make_msg()]
    hist_mock.next_cursor = ""

    with patch("src.deps.get_auth_stub") as mock_auth, \
         patch("src.routes.messages.get_messaging_stub") as mock_msg:
        auth_stub = MagicMock()
        auth_stub.ValidateToken.return_value = _valid_identity()
        mock_auth.return_value = auth_stub

        msg_stub = MagicMock()
        msg_stub.GetMessageHistory.return_value = hist_mock
        mock_msg.return_value = msg_stub

        resp = client.get(
            "/api/messages/group/g1/",
            headers={"Authorization": "Bearer valid.token"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    msg = data["results"][0]
    assert msg["sender"]["id"] == "u1"
    assert msg["sender"]["username"] == "alice"
    assert msg["group"] == "g1"
    assert "group_id" not in msg
    assert "next" in data


def test_private_history_alias(client):
    hist_mock = MagicMock()
    hist_mock.messages = []
    hist_mock.next_cursor = ""

    with patch("src.deps.get_auth_stub") as mock_auth, \
         patch("src.routes.messages.get_messaging_stub") as mock_msg:
        auth_stub = MagicMock()
        auth_stub.ValidateToken.return_value = _valid_identity()
        mock_auth.return_value = auth_stub

        msg_stub = MagicMock()
        msg_stub.GetMessageHistory.return_value = hist_mock
        mock_msg.return_value = msg_stub

        resp = client.get(
            "/api/messages/private/u2/",
            headers={"Authorization": "Bearer valid.token"},
        )

    assert resp.status_code == 200
    call_arg = msg_stub.GetMessageHistory.call_args[0][0]
    assert call_arg.private_with_user_id == "u2"


def test_conversations_normalized(client):
    conv = MagicMock()
    conv.type = "private"
    conv.conversation_id = "u2"
    conv.display_name = "u2"
    conv.last_message_preview = "hi"
    conv.last_message_at.ToDatetime.return_value = datetime(2024, 1, 1)

    convos_mock = MagicMock()
    convos_mock.conversations = [conv]

    profile = MagicMock()
    profile.username = "Bob"

    with patch("src.deps.get_auth_stub") as mock_auth, \
         patch("src.routes.messages.get_messaging_stub") as mock_msg, \
         patch("src.routes.messages.get_users_stub") as mock_users:
        auth_stub = MagicMock()
        auth_stub.ValidateToken.return_value = _valid_identity()
        mock_auth.return_value = auth_stub

        msg_stub = MagicMock()
        msg_stub.ListConversations.return_value = convos_mock
        mock_msg.return_value = msg_stub

        users_stub = MagicMock()
        users_stub.GetProfile.return_value = profile
        mock_users.return_value = users_stub

        resp = client.get(
            "/api/messages/conversations/",
            headers={"Authorization": "Bearer valid.token"},
        )

    assert resp.status_code == 200
    c = resp.json()[0]
    assert c["kind"] == "private"
    assert c["name"] == "Bob"
    assert c["last_message"]["content"] == "hi"
