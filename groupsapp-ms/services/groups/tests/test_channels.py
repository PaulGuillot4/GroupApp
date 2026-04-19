import uuid
import pytest
import grpc
from unittest.mock import MagicMock
from generated import groups_pb2
from src.main import GroupsServicer


@pytest.fixture
def servicer(engine):
    return GroupsServicer(engine)


@pytest.fixture
def existing_group(servicer):
    owner_id = str(uuid.uuid4())
    req = groups_pb2.CreateGroupRequest(
        owner_id=owner_id, name="ChannelGroup",
        description="", subscription_type="free",
    )
    return servicer.CreateGroup(req, MagicMock())


def test_create_channel(servicer, existing_group):
    req = groups_pb2.CreateChannelRequest(
        group_id=existing_group.id,
        name="general",
        description="General channel",
    )
    ctx = MagicMock()
    ch = servicer.CreateChannel(req, ctx)
    assert ch.id != ""
    assert ch.name == "general"
    assert ch.group_id == existing_group.id
    ctx.set_code.assert_not_called()


def test_list_channels(servicer, existing_group):
    for name in ["alpha", "beta"]:
        servicer.CreateChannel(
            groups_pb2.CreateChannelRequest(
                group_id=existing_group.id, name=name, description=""
            ),
            MagicMock(),
        )
    req = groups_pb2.GetGroupRequest(group_id=existing_group.id)
    ctx = MagicMock()
    resp = servicer.ListChannels(req, ctx)
    names = [c.name for c in resp.channels]
    assert "alpha" in names
    assert "beta" in names


def test_get_channel(servicer, existing_group):
    ch = servicer.CreateChannel(
        groups_pb2.CreateChannelRequest(
            group_id=existing_group.id, name="test-ch", description="Desc"
        ),
        MagicMock(),
    )
    req = groups_pb2.GetChannelRequest(channel_id=ch.id)
    ctx = MagicMock()
    resp = servicer.GetChannel(req, ctx)
    assert resp.channel.id == ch.id
    assert resp.channel.name == "test-ch"
    assert resp.group_id == existing_group.id


def test_get_channel_not_found(servicer):
    req = groups_pb2.GetChannelRequest(channel_id=str(uuid.uuid4()))
    ctx = MagicMock()
    servicer.GetChannel(req, ctx)
    ctx.set_code.assert_called_with(grpc.StatusCode.NOT_FOUND)
