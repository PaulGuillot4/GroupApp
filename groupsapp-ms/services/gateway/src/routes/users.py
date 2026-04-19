from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import grpc

from generated import auth_pb2, users_pb2
from ..clients import get_auth_stub, get_users_stub
from ..deps import get_current_user

router = APIRouter(prefix="/api/users", tags=["users"])


class UserResponse(BaseModel):
    user_id: str
    username: str
    email: str


class UserSummaryResponse(BaseModel):
    user_id: str
    username: str
    avatar_url: str


@router.get("/me", response_model=UserResponse)
def get_me(current_user: dict = Depends(get_current_user)):
    stub = get_auth_stub()
    try:
        user = stub.GetUserById(
            auth_pb2.GetUserByIdRequest(user_id=current_user["user_id"])
        )
        return UserResponse(user_id=user.id, username=user.username, email=user.email)
    except grpc.RpcError as exc:
        if exc.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail="User not found")
        raise HTTPException(status_code=500, detail="Auth service error")


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
                user_id=u.user_id, username=u.username, avatar_url=u.avatar_url
            )
            for u in resp.users
        ]
    except grpc.RpcError:
        raise HTTPException(status_code=503, detail="Users service unavailable")
