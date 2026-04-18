import grpc
from generated import messaging_pb2_grpc, common_pb2

def test_stub_creation():
    channel = grpc.insecure_channel("localhost:50054")
    stub = messaging_pb2_grpc.MessagingServiceStub(channel)
    assert stub is not None
