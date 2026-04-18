import pytest
import grpc
from unittest.mock import MagicMock
from accounts.models import User


@pytest.fixture
def servicer():
    import os
    import django
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "auth_service.settings")
    django.setup()
    from grpc_server import AuthServicer
    return AuthServicer()


@pytest.mark.django_db
def test_register_creates_user_and_returns_tokens(servicer):
    from generated.auth_pb2 import RegisterRequest
    context = MagicMock()
    req = RegisterRequest(username="alice", email="alice@example.com", password="securepass123")
    resp = servicer.Register(req, context)

    context.abort.assert_not_called()
    assert resp.access_token != ""
    assert resp.refresh_token != ""
    assert resp.user.username == "alice"
    assert resp.user.email == "alice@example.com"
    assert User.objects.filter(username="alice").exists()


@pytest.mark.django_db
def test_register_duplicate_username_aborts(servicer):
    from generated.auth_pb2 import RegisterRequest
    User.objects.create_user(username="bob", email="bob@example.com", password="pass")
    context = MagicMock()
    req = RegisterRequest(username="bob", email="other@example.com", password="pass")
    servicer.Register(req, context)
    context.abort.assert_called_once_with(grpc.StatusCode.ALREADY_EXISTS, "Username already taken")


@pytest.mark.django_db
def test_register_duplicate_email_aborts(servicer):
    from generated.auth_pb2 import RegisterRequest
    User.objects.create_user(username="carol", email="carol@example.com", password="pass")
    context = MagicMock()
    req = RegisterRequest(username="carol2", email="carol@example.com", password="pass")
    servicer.Register(req, context)
    context.abort.assert_called_once_with(grpc.StatusCode.ALREADY_EXISTS, "Email already registered")


@pytest.mark.django_db
def test_login_valid_credentials_returns_tokens(servicer):
    from generated.auth_pb2 import LoginRequest
    User.objects.create_user(username="dave", email="dave@example.com", password="secret123")
    context = MagicMock()
    req = LoginRequest(username="dave", password="secret123")
    resp = servicer.Login(req, context)

    context.abort.assert_not_called()
    assert resp.access_token != ""
    assert resp.user.username == "dave"


@pytest.mark.django_db
def test_login_wrong_password_aborts(servicer):
    from generated.auth_pb2 import LoginRequest
    User.objects.create_user(username="eve", email="eve@example.com", password="correct")
    context = MagicMock()
    req = LoginRequest(username="eve", password="wrong")
    servicer.Login(req, context)
    context.abort.assert_called_once_with(grpc.StatusCode.UNAUTHENTICATED, "Invalid credentials")
