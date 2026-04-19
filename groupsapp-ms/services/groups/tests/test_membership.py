import uuid
import pytest
import grpc
from unittest.mock import MagicMock
from generated import groups_pb2, common_pb2
from src.main import GroupsServicer


@pytest.fixture
def servicer(engine):
    return GroupsServicer(engine)


@pytest.fixture
def group_with_owner(servicer):
    owner_id = str(uuid.uuid4())
    req = groups_pb2.CreateGroupRequest(
        owner_id=owner_id, name="MembershipGroup",
        description="", subscription_type="free",
    )
    ctx = MagicMock()
    group = servicer.CreateGroup(req, ctx)
    return group, owner_id


def test_verify_membership_owner_is_member(servicer, group_with_owner):
    group, owner_id = group_with_owner
    req = groups_pb2.MembershipRequest(user_id=owner_id, group_id=group.id)
    ctx = MagicMock()
    info = servicer.VerifyMembership(req, ctx)
    assert info.is_member is True
    assert info.role == "owner"


def test_verify_membership_not_member(servicer, group_with_owner):
    group, _ = group_with_owner
    req = groups_pb2.MembershipRequest(user_id=str(uuid.uuid4()), group_id=group.id)
    ctx = MagicMock()
    info = servicer.VerifyMembership(req, ctx)
    assert info.is_member is False
    assert info.role == ""


def test_add_member(servicer, group_with_owner):
    group, _ = group_with_owner
    new_user = str(uuid.uuid4())
    req = groups_pb2.MembershipRequest(user_id=new_user, group_id=group.id)
    ctx = MagicMock()
    resp = servicer.AddMember(req, ctx)
    assert resp == common_pb2.Empty()
    ctx.set_code.assert_not_called()
    info = servicer.VerifyMembership(req, MagicMock())
    assert info.is_member is True
    assert info.role == "member"


def test_add_member_idempotent(servicer, group_with_owner):
    group, _ = group_with_owner
    uid = str(uuid.uuid4())
    req = groups_pb2.MembershipRequest(user_id=uid, group_id=group.id)
    servicer.AddMember(req, MagicMock())
    resp = servicer.AddMember(req, MagicMock())
    assert resp == common_pb2.Empty()


def test_remove_member(servicer, group_with_owner):
    group, _ = group_with_owner
    new_user = str(uuid.uuid4())
    add_req = groups_pb2.MembershipRequest(user_id=new_user, group_id=group.id)
    servicer.AddMember(add_req, MagicMock())
    rem_req = groups_pb2.MembershipRequest(user_id=new_user, group_id=group.id)
    ctx = MagicMock()
    resp = servicer.RemoveMember(rem_req, ctx)
    assert resp == common_pb2.Empty()
    info = servicer.VerifyMembership(rem_req, MagicMock())
    assert info.is_member is False


def test_join_group(servicer, group_with_owner):
    group, _ = group_with_owner
    joiner_id = str(uuid.uuid4())
    req = groups_pb2.MembershipRequest(user_id=joiner_id, group_id=group.id)
    ctx = MagicMock()
    resp = servicer.JoinGroup(req, ctx)
    assert resp == common_pb2.Empty()
    info = servicer.VerifyMembership(req, MagicMock())
    assert info.is_member is True
    assert info.role == "member"


def test_leave_group(servicer, group_with_owner):
    group, _ = group_with_owner
    joiner_id = str(uuid.uuid4())
    join_req = groups_pb2.MembershipRequest(user_id=joiner_id, group_id=group.id)
    servicer.JoinGroup(join_req, MagicMock())
    ctx = MagicMock()
    resp = servicer.LeaveGroup(join_req, ctx)
    assert resp == common_pb2.Empty()
    info = servicer.VerifyMembership(join_req, MagicMock())
    assert info.is_member is False


def test_list_members(servicer, group_with_owner):
    group, owner_id = group_with_owner
    extra_user = str(uuid.uuid4())
    servicer.AddMember(
        groups_pb2.MembershipRequest(user_id=extra_user, group_id=group.id),
        MagicMock(),
    )
    req = groups_pb2.GetGroupRequest(group_id=group.id)
    ctx = MagicMock()
    resp = servicer.ListMembers(req, ctx)
    user_ids = [m.user_id for m in resp.members]
    assert owner_id in user_ids
    assert extra_user in user_ids


def test_change_role(servicer, group_with_owner):
    group, _ = group_with_owner
    member_id = str(uuid.uuid4())
    servicer.AddMember(
        groups_pb2.MembershipRequest(user_id=member_id, group_id=group.id),
        MagicMock(),
    )
    req = groups_pb2.ChangeRoleRequest(
        user_id=member_id, group_id=group.id, role="moderator"
    )
    ctx = MagicMock()
    resp = servicer.ChangeRole(req, ctx)
    assert resp == common_pb2.Empty()
    info = servicer.VerifyMembership(
        groups_pb2.MembershipRequest(user_id=member_id, group_id=group.id),
        MagicMock(),
    )
    assert info.role == "moderator"
