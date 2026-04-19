from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import grpc

from generated import auth_pb2
from ..clients import get_auth_stub

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    user_id: str
    username: str
    email: str


def _to_token_response(resp) -> TokenResponse:
    return TokenResponse(
        access_token=resp.access_token,
        refresh_token=resp.refresh_token,
        user_id=resp.user.id,
        username=resp.user.username,
        email=resp.user.email,
    )


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: RegisterRequest):
    stub = get_auth_stub()
    try:
        resp = stub.Register(
            auth_pb2.RegisterRequest(
                username=body.username,
                email=body.email,
                password=body.password,
            )
        )
        return _to_token_response(resp)
    except grpc.RpcError as exc:
        if exc.code() == grpc.StatusCode.ALREADY_EXISTS:
            raise HTTPException(status_code=409, detail=exc.details())
        raise HTTPException(status_code=500, detail="Auth service error")


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    stub = get_auth_stub()
    try:
        resp = stub.Login(
            auth_pb2.LoginRequest(username=body.username, password=body.password)
        )
        return _to_token_response(resp)
    except grpc.RpcError as exc:
        if exc.code() == grpc.StatusCode.UNAUTHENTICATED:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        raise HTTPException(status_code=500, detail="Auth service error")


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest):
    stub = get_auth_stub()
    try:
        resp = stub.Refresh(auth_pb2.RefreshRequest(refresh_token=body.refresh_token))
        return _to_token_response(resp)
    except grpc.RpcError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


@router.post("/logout", status_code=204)
def logout(body: RefreshRequest):
    stub = get_auth_stub()
    try:
        stub.Logout(auth_pb2.RefreshRequest(refresh_token=body.refresh_token))
    except grpc.RpcError:
        pass
