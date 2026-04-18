import sys
import os
from concurrent import futures

import grpc
from google.protobuf import timestamp_pb2

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from generated import files_pb2, files_pb2_grpc, common_pb2


class FilesServicer(files_pb2_grpc.FilesServiceServicer):
    def Healthcheck(self, request, context):
        ts = timestamp_pb2.Timestamp()
        ts.GetCurrentTime()
        return common_pb2.HealthcheckResponse(
            service="files", status="OK", checked_at=ts
        )


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    files_pb2_grpc.add_FilesServiceServicer_to_server(FilesServicer(), server)
    server.add_insecure_port("0.0.0.0:50055")
    server.start()
    print("Files gRPC server listening on :50055", flush=True)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
