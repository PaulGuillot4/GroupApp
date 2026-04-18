import sys
import os
from concurrent import futures

import grpc
from google.protobuf import timestamp_pb2

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from generated import users_pb2, users_pb2_grpc, common_pb2


class UsersServicer(users_pb2_grpc.UsersServiceServicer):
    def Healthcheck(self, request, context):
        ts = timestamp_pb2.Timestamp()
        ts.GetCurrentTime()
        return common_pb2.HealthcheckResponse(
            service="users", status="OK", checked_at=ts
        )


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    users_pb2_grpc.add_UsersServiceServicer_to_server(UsersServicer(), server)
    server.add_insecure_port("0.0.0.0:50052")
    server.start()
    print("Users gRPC server listening on :50052", flush=True)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
