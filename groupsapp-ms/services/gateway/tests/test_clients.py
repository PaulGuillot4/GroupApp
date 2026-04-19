from src.clients import get_auth_stub
from generated import auth_pb2_grpc


def test_get_auth_stub_returns_stub():
    stub = get_auth_stub()
    assert isinstance(stub, auth_pb2_grpc.AuthServiceStub)
