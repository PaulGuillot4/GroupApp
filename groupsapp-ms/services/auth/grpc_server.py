import os
import sys
from concurrent import futures

import django
import grpc
from django.core.management import call_command
from google.protobuf import timestamp_pb2

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "auth_service.settings")
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from generated import auth_pb2, auth_pb2_grpc, common_pb2


def _make_auth_response(user):
    from accounts.tokens import CustomRefreshToken
    refresh = CustomRefreshToken.for_user(user)
    return auth_pb2.AuthResponse(
        access_token=str(refresh.access_token),
        refresh_token=str(refresh),
        user=auth_pb2.AuthUser(
            id=str(user.id),
            username=user.username,
            email=user.email,
        ),
    )


class AuthServicer(auth_pb2_grpc.AuthServiceServicer):

    def Healthcheck(self, request, context):
        ts = timestamp_pb2.Timestamp()
        ts.GetCurrentTime()
        return common_pb2.HealthcheckResponse(
            service="auth", status="OK", checked_at=ts
        )

    def Register(self, request, context):
        from accounts.models import User
        if User.objects.filter(username=request.username).exists():
            context.abort(grpc.StatusCode.ALREADY_EXISTS, "Username already taken")
            return
        if User.objects.filter(email=request.email).exists():
            context.abort(grpc.StatusCode.ALREADY_EXISTS, "Email already registered")
            return
        user = User.objects.create_user(
            username=request.username,
            email=request.email,
            password=request.password,
        )
        return _make_auth_response(user)

    def Login(self, request, context):
        from django.contrib.auth import authenticate
        user = authenticate(username=request.username, password=request.password)
        if user is None:
            context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid credentials")
            return
        return _make_auth_response(user)

    def Refresh(self, request, context):
        pass  # implemented in Task 4

    def Logout(self, request, context):
        pass  # implemented in Task 4

    def ValidateToken(self, request, context):
        pass  # implemented in Task 5

    def GetUserById(self, request, context):
        pass  # implemented in Task 5

    def GetUserByUsername(self, request, context):
        pass  # implemented in Task 5


def serve():
    call_command("migrate", verbosity=0)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    auth_pb2_grpc.add_AuthServiceServicer_to_server(AuthServicer(), server)
    server.add_insecure_port("0.0.0.0:50051")
    server.start()
    print("Auth gRPC server listening on :50051", flush=True)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
