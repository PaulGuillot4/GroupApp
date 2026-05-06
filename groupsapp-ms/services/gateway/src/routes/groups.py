from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import grpc

from generated import groups_pb2, users_pb2
from ..clients import get_groups_stub, get_users_stub
from ..deps import get_current_user

router = APIRouter(prefix="/api/groups", tags=["groups"])


class CreateGroupBody(BaseModel):
    name: str
    description: str = ""
    subscription_type: str = "free"


class UpdateGroupBody(BaseModel):
    name: str
    description: str = ""
    subscription_type: str = "free"


class CreateChannelBody(BaseModel):
    name: str
    description: str = ""


class ChangeRoleBody(BaseModel):
    role: str


class AddMemberBody(BaseModel):
    userId: str


def _grpc_group(g) -> dict:
    return {
        "id": g.id,
        "name": g.name,
        "description": g.description,
        "owner_id": g.owner_id,
        "subscription_type": g.subscription_type,
        "avatar_url": g.avatar_url,
    }


def _handle_rpc_error(exc: grpc.RpcError):
    code = exc.code()
    if code == grpc.StatusCode.NOT_FOUND:
        raise HTTPException(status_code=404, detail=exc.details())
    if code == grpc.StatusCode.ALREADY_EXISTS:
        raise HTTPException(status_code=409, detail=exc.details())
    if code == grpc.StatusCode.PERMISSION_DENIED:
        raise HTTPException(status_code=403, detail=exc.details())
    raise HTTPException(status_code=500, detail="Groups service error")


@router.get("/me")
def list_my_groups(current_user: dict = Depends(get_current_user)):
    stub = get_groups_stub()
    try:
        resp = stub.ListUserGroups(
            groups_pb2.ListUserGroupsRequest(user_id=current_user["user_id"])
        )
        return [
            {"id": g.id, "name": g.name, "avatar_url": g.avatar_url, "role": g.role}
            for g in resp.groups
        ]
    except grpc.RpcError as e:
        _handle_rpc_error(e)


@router.get("/", include_in_schema=False)
def list_my_groups_root(current_user: dict = Depends(get_current_user)):
    """GET /api/groups/ alias for chat.js compatibility."""
    return list_my_groups(current_user=current_user)


@router.post("", status_code=201)
def create_group(body: CreateGroupBody, current_user: dict = Depends(get_current_user)):
    stub = get_groups_stub()
    try:
        g = stub.CreateGroup(groups_pb2.CreateGroupRequest(
            owner_id=current_user["user_id"],
            name=body.name,
            description=body.description,
            subscription_type=body.subscription_type,
        ))
        return _grpc_group(g)
    except grpc.RpcError as e:
        _handle_rpc_error(e)


@router.get("/{group_id}/membership")
def verify_membership(group_id: str, current_user: dict = Depends(get_current_user)):
    stub = get_groups_stub()
    try:
        info = stub.VerifyMembership(groups_pb2.MembershipRequest(
            user_id=current_user["user_id"], group_id=group_id
        ))
        return {"is_member": info.is_member, "role": info.role}
    except grpc.RpcError as e:
        _handle_rpc_error(e)


@router.get("/{group_id}/members")
def list_members(group_id: str, current_user: dict = Depends(get_current_user)):
    groups_stub = get_groups_stub()
    users_stub_inst = get_users_stub()
    try:
        resp = groups_stub.ListMembers(groups_pb2.GetGroupRequest(group_id=group_id))
        result = []
        for m in resp.members:
            try:
                profile = users_stub_inst.GetProfile(
                    users_pb2.GetProfileRequest(user_id=m.user_id)
                )
                username = profile.username
            except Exception:
                username = m.user_id
            result.append({"user": {"id": m.user_id, "username": username}, "role": m.role})
        return result
    except grpc.RpcError as e:
        _handle_rpc_error(e)


@router.post("/{group_id}/members/", status_code=204)
@router.post("/{group_id}/members", status_code=204)
def add_member(
    group_id: str,
    body: AddMemberBody,
    current_user: dict = Depends(get_current_user),
):
    stub = get_groups_stub()
    try:
        stub.AddMember(groups_pb2.MembershipRequest(user_id=body.userId, group_id=group_id))
    except grpc.RpcError as e:
        _handle_rpc_error(e)


@router.delete("/{group_id}/members/{user_id}", status_code=204)
def remove_member(
    group_id: str, user_id: str, current_user: dict = Depends(get_current_user)
):
    stub = get_groups_stub()
    try:
        stub.RemoveMember(
            groups_pb2.MembershipRequest(user_id=user_id, group_id=group_id)
        )
    except grpc.RpcError as e:
        _handle_rpc_error(e)


@router.post("/{group_id}/join", status_code=204)
def join_group(group_id: str, current_user: dict = Depends(get_current_user)):
    stub = get_groups_stub()
    try:
        stub.JoinGroup(groups_pb2.MembershipRequest(
            user_id=current_user["user_id"], group_id=group_id
        ))
    except grpc.RpcError as e:
        _handle_rpc_error(e)


@router.post("/{group_id}/leave", status_code=204)
def leave_group(group_id: str, current_user: dict = Depends(get_current_user)):
    stub = get_groups_stub()
    try:
        stub.LeaveGroup(groups_pb2.MembershipRequest(
            user_id=current_user["user_id"], group_id=group_id
        ))
    except grpc.RpcError as e:
        _handle_rpc_error(e)


@router.patch("/{group_id}/members/{user_id}/role", status_code=204)
def change_role(
    group_id: str,
    user_id: str,
    body: ChangeRoleBody,
    current_user: dict = Depends(get_current_user),
):
    stub = get_groups_stub()
    try:
        stub.ChangeRole(groups_pb2.ChangeRoleRequest(
            user_id=user_id, group_id=group_id, role=body.role
        ))
    except grpc.RpcError as e:
        _handle_rpc_error(e)


@router.get("/{group_id}/channels")
def list_channels(group_id: str, current_user: dict = Depends(get_current_user)):
    stub = get_groups_stub()
    try:
        resp = stub.ListChannels(groups_pb2.GetGroupRequest(group_id=group_id))
        return [
            {"id": c.id, "name": c.name, "description": c.description}
            for c in resp.channels
        ]
    except grpc.RpcError as e:
        _handle_rpc_error(e)


@router.post("/{group_id}/channels", status_code=201)
def create_channel(
    group_id: str,
    body: CreateChannelBody,
    current_user: dict = Depends(get_current_user),
):
    stub = get_groups_stub()
    try:
        ch = stub.CreateChannel(groups_pb2.CreateChannelRequest(
            group_id=group_id, name=body.name, description=body.description
        ))
        return {
            "id": ch.id, "group_id": ch.group_id,
            "name": ch.name, "description": ch.description,
        }
    except grpc.RpcError as e:
        _handle_rpc_error(e)


@router.get("/{group_id}")
def get_group(group_id: str, current_user: dict = Depends(get_current_user)):
    stub = get_groups_stub()
    try:
        g = stub.GetGroup(groups_pb2.GetGroupRequest(group_id=group_id))
        return _grpc_group(g)
    except grpc.RpcError as e:
        _handle_rpc_error(e)


@router.patch("/{group_id}")
def update_group(
    group_id: str,
    body: UpdateGroupBody,
    current_user: dict = Depends(get_current_user),
):
    stub = get_groups_stub()
    try:
        g = stub.UpdateGroup(groups_pb2.UpdateGroupRequest(
            group_id=group_id, name=body.name,
            description=body.description, subscription_type=body.subscription_type,
        ))
        return _grpc_group(g)
    except grpc.RpcError as e:
        _handle_rpc_error(e)


@router.delete("/{group_id}", status_code=204)
def delete_group(group_id: str, current_user: dict = Depends(get_current_user)):
    stub = get_groups_stub()
    try:
        stub.DeleteGroup(groups_pb2.DeleteGroupRequest(group_id=group_id))
    except grpc.RpcError as e:
        _handle_rpc_error(e)
