from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
import grpc
import pytest


@pytest.fixture
def client():
    from src.main import app
    return TestClient(app, raise_server_exceptions=True)


def _valid_identity():
    identity = MagicMock()
    identity.user_id = "user-uuid-1"
    identity.username = "testuser"
    return identity


def test_search_users_route_exists(client):
    with patch("src.deps.get_auth_stub") as mock_fn:
        stub = MagicMock()
        stub.ValidateToken.return_value = _valid_identity()
        mock_fn.return_value = stub
        with patch("src.routes.users.get_users_stub") as mock_users:
            users_stub = MagicMock()
            users_stub.SearchUsers.return_value = MagicMock(users=[])
            mock_users.return_value = users_stub
            resp = client.get(
                "/api/users/search?q=test",
                headers={"Authorization": "Bearer valid.token"},
            )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_create_group_route(client):
    with patch("src.deps.get_auth_stub") as mock_auth, \
         patch("src.routes.groups.get_groups_stub") as mock_groups:
        auth_stub = MagicMock()
        auth_stub.ValidateToken.return_value = _valid_identity()
        mock_auth.return_value = auth_stub

        group_mock = MagicMock()
        group_mock.id = "grp-uuid-1"
        group_mock.name = "New Group"
        group_mock.description = ""
        group_mock.owner_id = "user-uuid-1"
        group_mock.subscription_type = "free"
        group_mock.avatar_url = ""
        groups_stub = MagicMock()
        groups_stub.CreateGroup.return_value = group_mock
        mock_groups.return_value = groups_stub

        resp = client.post(
            "/api/groups",
            json={"name": "New Group", "description": "", "subscription_type": "free"},
            headers={"Authorization": "Bearer valid.token"},
        )
    assert resp.status_code == 201
    assert resp.json()["id"] == "grp-uuid-1"
    assert resp.json()["name"] == "New Group"


def test_verify_membership_route(client):
    with patch("src.deps.get_auth_stub") as mock_auth, \
         patch("src.routes.groups.get_groups_stub") as mock_groups:
        auth_stub = MagicMock()
        auth_stub.ValidateToken.return_value = _valid_identity()
        mock_auth.return_value = auth_stub

        info_mock = MagicMock()
        info_mock.is_member = True
        info_mock.role = "owner"
        groups_stub = MagicMock()
        groups_stub.VerifyMembership.return_value = info_mock
        mock_groups.return_value = groups_stub

        resp = client.get(
            "/api/groups/grp-uuid-1/membership",
            headers={"Authorization": "Bearer valid.token"},
        )
    assert resp.status_code == 200
    assert resp.json() == {"is_member": True, "role": "owner"}


def test_groups_route_requires_auth(client):
    resp = client.post("/api/groups", json={"name": "test"})
    assert resp.status_code in (401, 403)


def test_list_my_groups_route(client):
    with patch("src.deps.get_auth_stub") as mock_auth, \
         patch("src.routes.groups.get_groups_stub") as mock_groups:
        auth_stub = MagicMock()
        auth_stub.ValidateToken.return_value = _valid_identity()
        mock_auth.return_value = auth_stub

        resp_mock = MagicMock()
        resp_mock.groups = []
        groups_stub = MagicMock()
        groups_stub.ListUserGroups.return_value = resp_mock
        mock_groups.return_value = groups_stub

        resp = client.get(
            "/api/groups/me",
            headers={"Authorization": "Bearer valid.token"},
        )
    assert resp.status_code == 200
    assert resp.json() == []
