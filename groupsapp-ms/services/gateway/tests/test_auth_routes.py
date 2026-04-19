from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
import grpc
import pytest


@pytest.fixture
def client():
    from src.main import app
    return TestClient(app)


def _mock_auth_response(username="alice", user_id="uuid-1", email="alice@example.com"):
    resp = MagicMock()
    resp.access_token = "access.token.here"
    resp.refresh_token = "refresh.token.here"
    resp.user.id = user_id
    resp.user.username = username
    resp.user.email = email
    return resp


def test_register_success(client):
    with patch("src.routes.auth.get_auth_stub") as mock_fn:
        stub = MagicMock()
        stub.Register.return_value = _mock_auth_response()
        mock_fn.return_value = stub

        resp = client.post("/api/auth/register", json={
            "username": "alice",
            "email": "alice@example.com",
            "password": "securepass123",
        })

    assert resp.status_code == 201
    data = resp.json()
    assert data["access_token"] == "access.token.here"
    assert data["username"] == "alice"


def test_register_conflict_returns_409(client):
    with patch("src.routes.auth.get_auth_stub") as mock_fn:
        stub = MagicMock()
        err = grpc.RpcError()
        err.code = lambda: grpc.StatusCode.ALREADY_EXISTS
        err.details = lambda: "Username already taken"
        stub.Register.side_effect = err
        mock_fn.return_value = stub

        resp = client.post("/api/auth/register", json={
            "username": "alice",
            "email": "alice@example.com",
            "password": "securepass123",
        })

    assert resp.status_code == 409


def test_login_success(client):
    with patch("src.routes.auth.get_auth_stub") as mock_fn:
        stub = MagicMock()
        stub.Login.return_value = _mock_auth_response()
        mock_fn.return_value = stub

        resp = client.post("/api/auth/login", json={
            "username": "alice",
            "password": "securepass123",
        })

    assert resp.status_code == 200
    assert resp.json()["access_token"] == "access.token.here"


def test_login_invalid_credentials_returns_401(client):
    with patch("src.routes.auth.get_auth_stub") as mock_fn:
        stub = MagicMock()
        err = grpc.RpcError()
        err.code = lambda: grpc.StatusCode.UNAUTHENTICATED
        err.details = lambda: "Invalid credentials"
        stub.Login.side_effect = err
        mock_fn.return_value = stub

        resp = client.post("/api/auth/login", json={
            "username": "alice",
            "password": "wrong",
        })

    assert resp.status_code == 401


def test_refresh_success(client):
    with patch("src.routes.auth.get_auth_stub") as mock_fn:
        stub = MagicMock()
        stub.Refresh.return_value = _mock_auth_response()
        mock_fn.return_value = stub

        resp = client.post("/api/auth/refresh", json={"refresh_token": "old.token"})

    assert resp.status_code == 200
    assert resp.json()["refresh_token"] == "refresh.token.here"


def test_logout_success(client):
    with patch("src.routes.auth.get_auth_stub") as mock_fn:
        stub = MagicMock()
        stub.Logout.return_value = MagicMock()
        mock_fn.return_value = stub

        resp = client.post("/api/auth/logout", json={"refresh_token": "some.token"})

    assert resp.status_code == 204
