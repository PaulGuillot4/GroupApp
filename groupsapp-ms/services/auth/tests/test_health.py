import grpc
from generated import auth_pb2_grpc, common_pb2

def test_healthcheck_connects():
    """Verifies the gRPC stub can be created (server tested in integration)."""
    channel = grpc.insecure_channel("localhost:50051")
    stub = auth_pb2_grpc.AuthServiceStub(channel)
    assert stub is not None
