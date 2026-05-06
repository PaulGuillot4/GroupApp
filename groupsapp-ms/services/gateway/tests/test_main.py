import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from src.main import app
    return TestClient(app)


def test_static_js_is_served(client):
    resp = client.get("/static/js/chat.js")
    assert resp.status_code == 200
    assert "javascript" in resp.headers.get("content-type", "")


def test_health_still_works(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "OK"
