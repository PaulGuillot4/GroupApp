import grpc
from generated import users_pb2_grpc, common_pb2

def test_stub_creation():
    channel = grpc.insecure_channel("localhost:50052")
    stub = users_pb2_grpc.UsersServiceStub(channel)
    assert stub is not None
