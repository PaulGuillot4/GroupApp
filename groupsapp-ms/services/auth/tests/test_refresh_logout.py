import pytest
import grpc
from unittest.mock import MagicMock
from accounts.models import User
from accounts.tokens import CustomRefreshToken


@pytest.fixture
def servicer():
    from grpc_server import AuthServicer
    return AuthServicer()


@pytest.fixture
def user_with_tokens(db):
    user = User.objects.create_user(
        username="frank", email="frank@example.com", password="pass123"
    )
    refresh = CustomRefreshToken.for_user(user)
    return user, str(refresh.access_token), str(refresh)


@pytest.mark.django_db
def test_refresh_returns_new_tokens(servicer, user_with_tokens):
    from generated.auth_pb2 import RefreshRequest
    _, _, refresh_token = user_with_tokens
    context = MagicMock()
    req = RefreshRequest(refresh_token=refresh_token)
    resp = servicer.Refresh(req, context)

    context.abort.assert_not_called()
    assert resp.access_token != ""
    assert resp.refresh_token != ""
    assert resp.refresh_token != refresh_token  # rotated


@pytest.mark.django_db
def test_refresh_invalid_token_aborts(servicer):
    from generated.auth_pb2 import RefreshRequest
    context = MagicMock()
    req = RefreshRequest(refresh_token="not.a.valid.token")
    servicer.Refresh(req, context)
    context.abort.assert_called_once()
    assert context.abort.call_args[0][0] == grpc.StatusCode.UNAUTHENTICATED


@pytest.mark.django_db
def test_logout_blacklists_token(servicer, user_with_tokens):
    from generated.auth_pb2 import RefreshRequest
    _, _, refresh_token = user_with_tokens
    context = MagicMock()
    req = RefreshRequest(refresh_token=refresh_token)
    servicer.Logout(req, context)
    context.abort.assert_not_called()

    # Using the same refresh token again should now fail
    context2 = MagicMock()
    servicer.Refresh(RefreshRequest(refresh_token=refresh_token), context2)
    context2.abort.assert_called_once()
    assert context2.abort.call_args[0][0] == grpc.StatusCode.UNAUTHENTICATED


@pytest.mark.django_db
def test_logout_invalid_token_aborts(servicer):
    from generated.auth_pb2 import RefreshRequest
    context = MagicMock()
    req = RefreshRequest(refresh_token="bad.token")
    servicer.Logout(req, context)
    context.abort.assert_called_once()
    assert context.abort.call_args[0][0] == grpc.StatusCode.UNAUTHENTICATED
