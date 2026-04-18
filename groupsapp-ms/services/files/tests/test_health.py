import grpc
from generated import files_pb2_grpc, common_pb2

def test_stub_creation():
    channel = grpc.insecure_channel("localhost:50055")
    stub = files_pb2_grpc.FilesServiceStub(channel)
    assert stub is not None
