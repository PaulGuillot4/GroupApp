from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
import grpc
import pytest


@pytest.fixture
def client():
    from src.main import app
    return TestClient(app, raise_server_exceptions=True)


def test_get_me_returns_user_profile(client):
    mock_identity = MagicMock()
    mock_identity.user_id = "uuid-999"
    mock_identity.username = "jack"

    mock_user = MagicMock()
    mock_user.id = "uuid-999"
    mock_user.username = "jack"
    mock_user.email = "jack@example.com"

    with patch("src.deps.get_auth_stub") as mock_validate_fn, \
         patch("src.routes.users.get_auth_stub") as mock_get_fn:

        validate_stub = MagicMock()
        validate_stub.ValidateToken.return_value = mock_identity
        mock_validate_fn.return_value = validate_stub

        get_stub = MagicMock()
        get_stub.GetUserById.return_value = mock_user
        mock_get_fn.return_value = get_stub

        resp = client.get(
            "/api/users/me",
            headers={"Authorization": "Bearer valid.access.token"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "jack"
    assert data["email"] == "jack@example.com"
    assert data["user_id"] == "uuid-999"


def test_get_me_no_token_returns_403(client):
    # FastAPI 0.100+ / Starlette returns 401 (not authenticated) when
    # HTTPBearer finds no Authorization header; older versions returned 403.
    resp = client.get("/api/users/me")
    assert resp.status_code in (401, 403)


def test_get_me_invalid_token_returns_401(client):
    with patch("src.deps.get_auth_stub") as mock_fn:
        stub = MagicMock()
        stub.ValidateToken.side_effect = grpc.RpcError()
        mock_fn.return_value = stub

        resp = client.get(
            "/api/users/me",
            headers={"Authorization": "Bearer bad.token"},
        )

    assert resp.status_code == 401
