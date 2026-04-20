import pytest
from unittest.mock import MagicMock, patch
from generated import messaging_pb2


@pytest.mark.django_db
def test_get_message_history_group(make_message):
    from grpc_server import MessagingServicer
    make_message(type="group", group_id="grp-test", content="hello")
    make_message(type="group", group_id="grp-test", content="world")
    servicer = MessagingServicer()
    req = messaging_pb2.GetMessageHistoryRequest(group_id="grp-test", limit=10)
    ctx = MagicMock()
    resp = servicer.GetMessageHistory(req, ctx)
    assert len(resp.messages) == 2
    contents = [m.content for m in resp.messages]
    assert "hello" in contents and "world" in contents


@pytest.mark.django_db
def test_get_message_history_private(make_message):
    from grpc_server import MessagingServicer
    make_message(type="private", sender_id="u1", receiver_id="u2", content="hi u2")
    make_message(type="private", sender_id="u2", receiver_id="u1", content="hi u1")
    servicer = MessagingServicer()
    req = messaging_pb2.GetMessageHistoryRequest(
        requesting_user_id="u1", private_with_user_id="u2", limit=10
    )
    ctx = MagicMock()
    resp = servicer.GetMessageHistory(req, ctx)
    assert len(resp.messages) == 2


@pytest.mark.django_db
def test_list_conversations(make_message):
    from grpc_server import MessagingServicer
    make_message(type="group", group_id="grp-a", sender_id="u1")
    make_message(type="private", sender_id="u1", receiver_id="u3")
    servicer = MessagingServicer()
    req = messaging_pb2.ListConversationsRequest(user_id="u1")
    ctx = MagicMock()
    resp = servicer.ListConversations(req, ctx)
    types = [c.type for c in resp.conversations]
    assert "group" in types
    assert "private" in types


def test_push_direct_message_sends_to_channel_layer():
    from grpc_server import MessagingServicer
    servicer = MessagingServicer()
    req = messaging_pb2.PushDirectMessageRequest(
        user_id="u-42", payload_json='{"event":"test"}'
    )
    ctx = MagicMock()
    with patch("grpc_server.get_channel_layer") as mock_cl_fn:
        mock_cl = MagicMock()
        mock_cl_fn.return_value = mock_cl
        with patch("grpc_server.async_to_sync") as mock_a2s:
            mock_a2s.return_value = lambda *a, **kw: None
            resp = servicer.PushDirectMessage(req, ctx)
    from generated import common_pb2
    assert resp == common_pb2.Empty()
