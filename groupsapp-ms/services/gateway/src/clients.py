import os
import grpc
from generated import auth_pb2_grpc, users_pb2_grpc, groups_pb2_grpc, messaging_pb2_grpc, files_pb2_grpc

AUTH_SERVICE_ADDR = os.getenv("AUTH_GRPC", os.getenv("AUTH_SERVICE_ADDR", "localhost:50051"))
USERS_SERVICE_ADDR = os.getenv("USERS_GRPC", "localhost:50052")
GROUPS_SERVICE_ADDR = os.getenv("GROUPS_GRPC", "localhost:50053")
MESSAGING_SERVICE_ADDR = os.getenv("MESSAGING_GRPC", "localhost:50054")
FILES_SERVICE_ADDR = os.getenv("FILES_GRPC", "localhost:50055")


def get_auth_stub() -> auth_pb2_grpc.AuthServiceStub:
    return auth_pb2_grpc.AuthServiceStub(grpc.insecure_channel(AUTH_SERVICE_ADDR))


def get_users_stub() -> users_pb2_grpc.UsersServiceStub:
    return users_pb2_grpc.UsersServiceStub(grpc.insecure_channel(USERS_SERVICE_ADDR))


def get_groups_stub() -> groups_pb2_grpc.GroupsServiceStub:
    return groups_pb2_grpc.GroupsServiceStub(grpc.insecure_channel(GROUPS_SERVICE_ADDR))


def get_messaging_stub() -> messaging_pb2_grpc.MessagingServiceStub:
    return messaging_pb2_grpc.MessagingServiceStub(grpc.insecure_channel(MESSAGING_SERVICE_ADDR))


def get_files_stub() -> files_pb2_grpc.FilesServiceStub:
    return files_pb2_grpc.FilesServiceStub(grpc.insecure_channel(FILES_SERVICE_ADDR))
