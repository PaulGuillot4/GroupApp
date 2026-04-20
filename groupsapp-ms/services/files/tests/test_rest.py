import io
import pytest
from fastapi.testclient import TestClient
from src.rest import app


@pytest.fixture
def client(engine):
    return TestClient(app)


def test_upload_file(client):
    content = b"fake image data"
    resp = client.post(
        "/upload",
        files={"file": ("test.jpg", io.BytesIO(content), "image/jpeg")},
        headers={"x-user-id": "user-rest-1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "file_id" in data
    assert "url" in data
    assert data["mime_type"] == "image/jpeg"


def test_upload_requires_file(client):
    resp = client.post("/upload", headers={"x-user-id": "user-1"})
    assert resp.status_code == 422
