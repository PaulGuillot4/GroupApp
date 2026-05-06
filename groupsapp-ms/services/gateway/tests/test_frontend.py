from fastapi.testclient import TestClient
import pytest


@pytest.fixture
def client():
    from src.main import app
    return TestClient(app)


def test_root_redirects_to_login(client):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"] == "/auth/login/"


def test_login_page_returns_html(client):
    resp = client.get("/auth/login/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_register_page_returns_html(client):
    resp = client.get("/auth/register/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_app_page_returns_html(client):
    resp = client.get("/app/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
