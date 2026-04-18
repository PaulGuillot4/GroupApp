import grpc
from generated import groups_pb2_grpc, common_pb2

def test_stub_creation():
    channel = grpc.insecure_channel("localhost:50053")
    stub = groups_pb2_grpc.GroupsServiceStub(channel)
    assert stub is not None
