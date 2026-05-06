import os
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import grpc
import httpx

from generated import auth_pb2, users_pb2
from ..clients import get_auth_stub, get_users_stub
from ..deps import get_current_user

router = APIRouter(prefix="/api/users", tags=["users"])

USERS_HTTP_URL = os.getenv("USERS_HTTP", "http://users:8003")


class UserResponse(BaseModel):
    user_id: str
    id: str
    username: str
    email: str


class UserSummaryResponse(BaseModel):
    user_id: str
    id: str
    username: str
    avatar_url: str


class UserProfileResponse(BaseModel):
    user_id: str
    username: str
    email: str
    avatar_url: str
    bio: str
    last_seen: str | None = None


class UpdateProfileBody(BaseModel):
    avatar_url: str = ""
    bio: str = ""


@router.get("/me", response_model=UserResponse)
def get_me(current_user: dict = Depends(get_current_user)):
    stub = get_auth_stub()
    try:
        user = stub.GetUserById(
            auth_pb2.GetUserByIdRequest(user_id=current_user["user_id"])
        )
        return UserResponse(user_id=user.id, id=user.id, username=user.username, email=user.email)
    except grpc.RpcError as exc:
        if exc.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail="User not found")
        raise HTTPException(status_code=500, detail="Auth service error")


@router.get("/me/profile", response_model=UserProfileResponse)
def get_my_profile(current_user: dict = Depends(get_current_user)):
    """Get the full profile of the authenticated user."""
    stub = get_users_stub()
    try:
        p = stub.GetProfile(users_pb2.GetProfileRequest(user_id=current_user["user_id"]))
        return UserProfileResponse(
            user_id=p.user_id,
            username=p.username,
            email=p.email,
            avatar_url=p.avatar_url,
            bio=p.bio,
            last_seen=p.last_seen.ToDatetime().isoformat() if p.HasField("last_seen") else None,
        )
    except grpc.RpcError as exc:
        if exc.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail="User not found")
        raise HTTPException(status_code=503, detail="Users service unavailable")


@router.patch("/me/profile", response_model=UserProfileResponse)
async def update_my_profile(
    body: UpdateProfileBody,
    current_user: dict = Depends(get_current_user),
):
    """Update avatar_url and/or bio for the authenticated user via Users REST."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.patch(
                f"{USERS_HTTP_URL}/profile",
                json=body.model_dump(),
                headers={"x-user-id": current_user["user_id"]},
                timeout=10.0,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code, detail="Profile update failed")
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Users service unavailable")
    data = resp.json()
    return UserProfileResponse(**data)


@router.get("/search", response_model=list[UserSummaryResponse])
def search_users(
    q: str,
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
):
    stub = get_users_stub()
    try:
        resp = stub.SearchUsers(users_pb2.SearchUsersRequest(query=q, limit=limit))
        return [
            UserSummaryResponse(
                user_id=u.user_id, id=u.user_id, username=u.username, avatar_url=u.avatar_url
            )
            for u in resp.users
        ]
    except grpc.RpcError:
        raise HTTPException(status_code=503, detail="Users service unavailable")


@router.get("/{user_id}/profile", response_model=UserProfileResponse)
def get_user_profile(
    user_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get the full profile of any user by user_id."""
    stub = get_users_stub()
    try:
        p = stub.GetProfile(users_pb2.GetProfileRequest(user_id=user_id))
        return UserProfileResponse(
            user_id=p.user_id,
            username=p.username,
            email=p.email,
            avatar_url=p.avatar_url,
            bio=p.bio,
            last_seen=p.last_seen.ToDatetime().isoformat() if p.HasField("last_seen") else None,
        )
    except grpc.RpcError as exc:
        if exc.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail="User not found")
        raise HTTPException(status_code=503, detail="Users service unavailable")
