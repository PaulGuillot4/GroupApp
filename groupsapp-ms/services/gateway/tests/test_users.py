from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from src.main import app
    return TestClient(app, raise_server_exceptions=True)


def test_get_me_includes_id_field(client):
    mock_identity = MagicMock()
    mock_identity.user_id = "user-uuid-1"
    mock_identity.username = "alice"

    mock_user = MagicMock()
    mock_user.id = "user-uuid-1"
    mock_user.username = "alice"
    mock_user.email = "alice@test.com"

    with patch("src.deps.get_auth_stub") as mock_auth, \
         patch("src.routes.users.get_auth_stub") as mock_get_user:
        auth_stub = MagicMock()
        auth_stub.ValidateToken.return_value = mock_identity
        mock_auth.return_value = auth_stub

        get_stub = MagicMock()
        get_stub.GetUserById.return_value = mock_user
        mock_get_user.return_value = get_stub

        resp = client.get(
            "/api/users/me",
            headers={"Authorization": "Bearer valid.token"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "user-uuid-1"
    assert data["user_id"] == "user-uuid-1"
