import os
import grpc
from generated import messaging_pb2_grpc, users_pb2_grpc

MESSAGING_GRPC = os.getenv("MESSAGING_GRPC", "localhost:50054")
USERS_GRPC = os.getenv("USERS_GRPC", "localhost:50052")


def get_messaging_stub():
    return messaging_pb2_grpc.MessagingServiceStub(
        grpc.insecure_channel(MESSAGING_GRPC)
    )


def get_users_stub():
    return users_pb2_grpc.UsersServiceStub(
        grpc.insecure_channel(USERS_GRPC)
    )
