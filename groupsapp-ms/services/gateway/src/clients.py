import os
import grpc
from generated import auth_pb2_grpc

AUTH_SERVICE_ADDR = os.getenv("AUTH_GRPC", os.getenv("AUTH_SERVICE_ADDR", "localhost:50051"))


def get_auth_stub() -> auth_pb2_grpc.AuthServiceStub:
    channel = grpc.insecure_channel(AUTH_SERVICE_ADDR)
    return auth_pb2_grpc.AuthServiceStub(channel)
