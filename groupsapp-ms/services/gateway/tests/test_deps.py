from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
import grpc
import pytest


def test_get_current_user_valid_token():
    from src.deps import get_current_user
    mock_identity = MagicMock()
    mock_identity.user_id = "uuid-123"
    mock_identity.username = "alice"

    with patch("src.deps.get_auth_stub") as mock_stub_fn:
        mock_stub = MagicMock()
        mock_stub.ValidateToken.return_value = mock_identity
        mock_stub_fn.return_value = mock_stub

        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid.token")
        result = get_current_user(credentials=creds)

    assert result == {"user_id": "uuid-123", "username": "alice"}


def test_get_current_user_invalid_token_raises_401():
    from src.deps import get_current_user
    with patch("src.deps.get_auth_stub") as mock_stub_fn:
        mock_stub = MagicMock()
        error = grpc.RpcError()
        mock_stub.ValidateToken.side_effect = error
        mock_stub_fn.return_value = mock_stub

        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="bad.token")
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(credentials=creds)

    assert exc_info.value.status_code == 401
