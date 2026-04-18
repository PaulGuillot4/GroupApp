import sys
import os
from concurrent import futures

import grpc
from google.protobuf import timestamp_pb2

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from generated import groups_pb2, groups_pb2_grpc, common_pb2


class GroupsServicer(groups_pb2_grpc.GroupsServiceServicer):
    def Healthcheck(self, request, context):
        ts = timestamp_pb2.Timestamp()
        ts.GetCurrentTime()
        return common_pb2.HealthcheckResponse(
            service="groups", status="OK", checked_at=ts
        )


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    groups_pb2_grpc.add_GroupsServiceServicer_to_server(GroupsServicer(), server)
    server.add_insecure_port("0.0.0.0:50053")
    server.start()
    print("Groups gRPC server listening on :50053", flush=True)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
