import os
from concurrent import futures

import django
import grpc
from google.protobuf import timestamp_pb2

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "auth_service.settings")
django.setup()

import sys
sys.path.insert(0, os.path.dirname(__file__))
from generated import auth_pb2, auth_pb2_grpc, common_pb2


class AuthServicer(auth_pb2_grpc.AuthServiceServicer):
    def Healthcheck(self, request, context):
        ts = timestamp_pb2.Timestamp()
        ts.GetCurrentTime()
        return common_pb2.HealthcheckResponse(
            service="auth", status="OK", checked_at=ts
        )


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    auth_pb2_grpc.add_AuthServiceServicer_to_server(AuthServicer(), server)
    server.add_insecure_port("0.0.0.0:50051")
    server.start()
    print("Auth gRPC server listening on :50051", flush=True)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
