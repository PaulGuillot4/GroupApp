import os
from concurrent import futures

import django
import grpc
from google.protobuf import timestamp_pb2

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "messaging_service.settings")
django.setup()

import sys
sys.path.insert(0, os.path.dirname(__file__))
from generated import messaging_pb2, messaging_pb2_grpc, common_pb2


class MessagingServicer(messaging_pb2_grpc.MessagingServiceServicer):
    def Healthcheck(self, request, context):
        ts = timestamp_pb2.Timestamp()
        ts.GetCurrentTime()
        return common_pb2.HealthcheckResponse(
            service="messaging", status="OK", checked_at=ts
        )


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    messaging_pb2_grpc.add_MessagingServiceServicer_to_server(MessagingServicer(), server)
    server.add_insecure_port("0.0.0.0:50054")
    server.start()
    print("Messaging gRPC server listening on :50054", flush=True)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
