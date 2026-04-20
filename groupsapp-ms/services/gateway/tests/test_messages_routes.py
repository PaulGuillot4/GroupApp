from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
import pytest


@pytest.fixture
def client():
    from src.main import app
    return TestClient(app, raise_server_exceptions=True)


def _valid_identity():
    identity = MagicMock()
    identity.user_id = "user-uuid-1"
    identity.username = "testuser"
    return identity


def test_get_history_requires_auth(client):
    resp = client.get("/api/messages/history?group_id=grp-1")
    assert resp.status_code in (401, 403)


def test_get_history_group(client):
    with patch("src.deps.get_auth_stub") as mock_auth, \
         patch("src.routes.messages.get_messaging_stub") as mock_msg:
        auth_stub = MagicMock()
        auth_stub.ValidateToken.return_value = _valid_identity()
        mock_auth.return_value = auth_stub

        hist_mock = MagicMock()
        hist_mock.messages = []
        hist_mock.next_cursor = ""
        msg_stub = MagicMock()
        msg_stub.GetMessageHistory.return_value = hist_mock
        mock_msg.return_value = msg_stub

        resp = client.get(
            "/api/messages/history?group_id=grp-1",
            headers={"Authorization": "Bearer valid.token"},
        )
    assert resp.status_code == 200
    assert "messages" in resp.json()


def test_list_conversations(client):
    with patch("src.deps.get_auth_stub") as mock_auth, \
         patch("src.routes.messages.get_messaging_stub") as mock_msg:
        auth_stub = MagicMock()
        auth_stub.ValidateToken.return_value = _valid_identity()
        mock_auth.return_value = auth_stub

        convos_mock = MagicMock()
        convos_mock.conversations = []
        msg_stub = MagicMock()
        msg_stub.ListConversations.return_value = convos_mock
        mock_msg.return_value = msg_stub

        resp = client.get(
            "/api/messages/conversations",
            headers={"Authorization": "Bearer valid.token"},
        )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
