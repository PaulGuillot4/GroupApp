from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import grpc

from generated import auth_pb2
from .clients import get_auth_stub

bearer = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
) -> dict:
    stub = get_auth_stub()
    try:
        identity = stub.ValidateToken(
            auth_pb2.ValidateTokenRequest(token=credentials.credentials)
        )
        return {"user_id": identity.user_id, "username": identity.username}
    except grpc.RpcError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
