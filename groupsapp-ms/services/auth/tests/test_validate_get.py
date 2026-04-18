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
def user_and_access(db):
    user = User.objects.create_user(
        username="grace", email="grace@example.com", password="pass123"
    )
    refresh = CustomRefreshToken.for_user(user)
    return user, str(refresh.access_token)


@pytest.mark.django_db
def test_validate_token_returns_identity(servicer, user_and_access):
    from generated.auth_pb2 import ValidateTokenRequest
    user, access_token = user_and_access
    context = MagicMock()
    resp = servicer.ValidateToken(ValidateTokenRequest(token=access_token), context)

    context.abort.assert_not_called()
    assert resp.user_id == str(user.id)
    assert resp.username == "grace"
    assert resp.expires_at > 0


@pytest.mark.django_db
def test_validate_token_invalid_aborts(servicer):
    from generated.auth_pb2 import ValidateTokenRequest
    context = MagicMock()
    servicer.ValidateToken(ValidateTokenRequest(token="bad.token.here"), context)
    context.abort.assert_called_once()
    assert context.abort.call_args[0][0] == grpc.StatusCode.UNAUTHENTICATED


@pytest.mark.django_db
def test_get_user_by_id_returns_user(servicer):
    from generated.auth_pb2 import GetUserByIdRequest
    user = User.objects.create_user(username="henry", email="h@example.com", password="p")
    context = MagicMock()
    resp = servicer.GetUserById(GetUserByIdRequest(user_id=str(user.id)), context)

    context.abort.assert_not_called()
    assert resp.username == "henry"
    assert resp.email == "h@example.com"


@pytest.mark.django_db
def test_get_user_by_id_not_found_aborts(servicer):
    from generated.auth_pb2 import GetUserByIdRequest
    import uuid
    context = MagicMock()
    servicer.GetUserById(GetUserByIdRequest(user_id=str(uuid.uuid4())), context)
    context.abort.assert_called_once_with(grpc.StatusCode.NOT_FOUND, "User not found")


@pytest.mark.django_db
def test_get_user_by_username_returns_user(servicer):
    from generated.auth_pb2 import GetUserByUsernameRequest
    User.objects.create_user(username="iris", email="iris@example.com", password="p")
    context = MagicMock()
    resp = servicer.GetUserByUsername(GetUserByUsernameRequest(username="iris"), context)

    context.abort.assert_not_called()
    assert resp.username == "iris"


@pytest.mark.django_db
def test_get_user_by_username_not_found_aborts(servicer):
    from generated.auth_pb2 import GetUserByUsernameRequest
    context = MagicMock()
    servicer.GetUserByUsername(GetUserByUsernameRequest(username="nobody"), context)
    context.abort.assert_called_once_with(grpc.StatusCode.NOT_FOUND, "User not found")
