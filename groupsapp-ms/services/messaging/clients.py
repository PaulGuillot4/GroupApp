import os
import grpc
from generated import auth_pb2_grpc, groups_pb2_grpc, users_pb2_grpc

AUTH_GRPC = os.getenv("AUTH_GRPC", "localhost:50051")
GROUPS_GRPC = os.getenv("GROUPS_GRPC", "localhost:50053")
USERS_GRPC = os.getenv("USERS_GRPC", "localhost:50052")


def get_auth_stub():
    return auth_pb2_grpc.AuthServiceStub(grpc.insecure_channel(AUTH_GRPC))


def get_groups_stub():
    return groups_pb2_grpc.GroupsServiceStub(grpc.insecure_channel(GROUPS_GRPC))


def get_users_stub():
    return users_pb2_grpc.UsersServiceStub(grpc.insecure_channel(USERS_GRPC))
