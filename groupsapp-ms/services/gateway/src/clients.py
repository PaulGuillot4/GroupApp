import os
import grpc
from generated import auth_pb2_grpc, users_pb2_grpc, groups_pb2_grpc

AUTH_SERVICE_ADDR = os.getenv("AUTH_GRPC", os.getenv("AUTH_SERVICE_ADDR", "localhost:50051"))
USERS_SERVICE_ADDR = os.getenv("USERS_GRPC", "localhost:50052")
GROUPS_SERVICE_ADDR = os.getenv("GROUPS_GRPC", "localhost:50053")


def get_auth_stub() -> auth_pb2_grpc.AuthServiceStub:
    channel = grpc.insecure_channel(AUTH_SERVICE_ADDR)
    return auth_pb2_grpc.AuthServiceStub(channel)


def get_users_stub() -> users_pb2_grpc.UsersServiceStub:
    channel = grpc.insecure_channel(USERS_SERVICE_ADDR)
    return users_pb2_grpc.UsersServiceStub(channel)


def get_groups_stub() -> groups_pb2_grpc.GroupsServiceStub:
    channel = grpc.insecure_channel(GROUPS_SERVICE_ADDR)
    return groups_pb2_grpc.GroupsServiceStub(channel)
