import io
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient
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


def test_get_file_metadata(client):
    with patch("src.deps.get_auth_stub") as mock_auth, \
         patch("src.routes.files.get_files_stub") as mock_files:
        auth_stub = MagicMock()
        auth_stub.ValidateToken.return_value = _valid_identity()
        mock_auth.return_value = auth_stub

        meta_mock = MagicMock()
        meta_mock.id = "file-1"
        meta_mock.url = "http://files:8002/files/file-1.jpg"
        meta_mock.mime_type = "image/jpeg"
        meta_mock.size = 1024
        meta_mock.owner_id = "user-uuid-1"
        files_stub = MagicMock()
        files_stub.GetFileMetadata.return_value = meta_mock
        mock_files.return_value = files_stub

        resp = client.get(
            "/api/files/file-1",
            headers={"Authorization": "Bearer valid.token"},
        )
    assert resp.status_code == 200
    assert resp.json()["id"] == "file-1"


def test_get_file_metadata_requires_auth(client):
    resp = client.get("/api/files/file-1")
    assert resp.status_code in (401, 403)
