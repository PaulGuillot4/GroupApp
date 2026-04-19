import uuid
import pytest
import grpc
from unittest.mock import MagicMock
from generated import groups_pb2, common_pb2
from src.main import GroupsServicer


@pytest.fixture
def servicer(engine):
    return GroupsServicer(engine)


def make_group(servicer, owner_id=None, name="Test Group"):
    owner_id = owner_id or str(uuid.uuid4())
    req = groups_pb2.CreateGroupRequest(
        owner_id=owner_id,
        name=name,
        description="A description",
        subscription_type="free",
    )
    ctx = MagicMock()
    return servicer.CreateGroup(req, ctx), owner_id


def test_create_group(servicer):
    group, owner_id = make_group(servicer)
    assert group.id != ""
    assert group.name == "Test Group"
    assert group.owner_id == owner_id
    assert group.subscription_type == "free"


def test_create_group_auto_adds_owner_as_member(servicer):
    group, owner_id = make_group(servicer, name="OwnerAutoMember")
    req = groups_pb2.MembershipRequest(user_id=owner_id, group_id=group.id)
    ctx = MagicMock()
    info = servicer.VerifyMembership(req, ctx)
    assert info.is_member is True
    assert info.role == "owner"


def test_get_group_found(servicer):
    group, _ = make_group(servicer, name="GetGroup Test")
    req = groups_pb2.GetGroupRequest(group_id=group.id)
    ctx = MagicMock()
    resp = servicer.GetGroup(req, ctx)
    assert resp.id == group.id
    assert resp.name == "GetGroup Test"


def test_get_group_not_found(servicer):
    req = groups_pb2.GetGroupRequest(group_id=str(uuid.uuid4()))
    ctx = MagicMock()
    servicer.GetGroup(req, ctx)
    ctx.set_code.assert_called_with(grpc.StatusCode.NOT_FOUND)


def test_update_group(servicer):
    group, _ = make_group(servicer, name="Original Name")
    req = groups_pb2.UpdateGroupRequest(
        group_id=group.id,
        name="Updated Name",
        description="New desc",
        subscription_type="premium",
    )
    ctx = MagicMock()
    resp = servicer.UpdateGroup(req, ctx)
    assert resp.name == "Updated Name"
    assert resp.subscription_type == "premium"


def test_delete_group(servicer):
    group, _ = make_group(servicer, name="ToDelete")
    req = groups_pb2.DeleteGroupRequest(group_id=group.id)
    ctx = MagicMock()
    resp = servicer.DeleteGroup(req, ctx)
    assert resp == common_pb2.Empty()
    get_ctx = MagicMock()
    servicer.GetGroup(groups_pb2.GetGroupRequest(group_id=group.id), get_ctx)
    get_ctx.set_code.assert_called_with(grpc.StatusCode.NOT_FOUND)


def test_list_user_groups(servicer):
    owner_id = str(uuid.uuid4())
    make_group(servicer, owner_id=owner_id, name="UserGroup1")
    make_group(servicer, owner_id=owner_id, name="UserGroup2")
    req = groups_pb2.ListUserGroupsRequest(user_id=owner_id)
    ctx = MagicMock()
    resp = servicer.ListUserGroups(req, ctx)
    names = [g.name for g in resp.groups]
    assert "UserGroup1" in names
    assert "UserGroup2" in names
