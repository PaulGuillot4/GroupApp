import sys
import os
import threading
from concurrent import futures
from datetime import timezone

import grpc
from google.protobuf import timestamp_pb2
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from generated import files_pb2, files_pb2_grpc, common_pb2
from src.db import get_engine
from src.models import metadata

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = get_engine()
    return _engine


class FilesServicer(files_pb2_grpc.FilesServiceServicer):
    def __init__(self, engine=None):
        self._engine = engine or _get_engine()

    def Healthcheck(self, request, context):
        ts = timestamp_pb2.Timestamp()
        ts.GetCurrentTime()
        return common_pb2.HealthcheckResponse(
            service="files", status="OK", checked_at=ts
        )

    def GetFileMetadata(self, request, context):
        with self._engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM files WHERE id = :id"), {"id": request.file_id}
            ).fetchone()
        if row is None:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("File not found")
            return files_pb2.FileMetadata()
        meta = files_pb2.FileMetadata(
            id=row.id,
            owner_id=row.owner_id,
            url=row.url,
            mime_type=row.mime_type,
            size=row.size,
        )
        if row.uploaded_at:
            dt = row.uploaded_at
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            ts = timestamp_pb2.Timestamp()
            ts.FromDatetime(dt)
            meta.uploaded_at.CopyFrom(ts)
        return meta


def serve_grpc():
    engine = _get_engine()
    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS files"))
        conn.commit()
    metadata.create_all(engine)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    files_pb2_grpc.add_FilesServiceServicer_to_server(FilesServicer(engine), server)
    server.add_insecure_port("0.0.0.0:50055")
    server.start()
    print("Files gRPC server listening on :50055", flush=True)
    server.wait_for_termination()


if __name__ == "__main__":
    grpc_thread = threading.Thread(target=serve_grpc, daemon=True)
    grpc_thread.start()

    import uvicorn
    from src.rest import app
    print("Files REST server starting on :8002", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=8002)
