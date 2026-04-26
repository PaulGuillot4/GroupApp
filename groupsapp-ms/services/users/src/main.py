import sys
import os
import threading
from concurrent import futures
from datetime import timezone

import grpc
from google.protobuf import timestamp_pb2
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from generated import users_pb2, users_pb2_grpc, common_pb2
from src.db import get_engine
from src.models import metadata, user_profiles

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = get_engine()
    return _engine


class UsersServicer(users_pb2_grpc.UsersServiceServicer):
    def __init__(self, engine=None):
        self._engine = engine or _get_engine()

    def Healthcheck(self, request, context):
        ts = timestamp_pb2.Timestamp()
        ts.GetCurrentTime()
        return common_pb2.HealthcheckResponse(
            service="users", status="OK", checked_at=ts
        )

    def GetProfile(self, request, context):
        with self._engine.connect() as conn:
            row = conn.execute(text("""
                SELECT au.id::text AS user_id,
                       au.username,
                       au.email,
                       COALESCE(up.avatar_url, '') AS avatar_url,
                       COALESCE(up.bio, '') AS bio,
                       up.last_seen
                FROM auth.users au
                LEFT JOIN user_profiles up ON au.id::text = up.user_id
                WHERE au.id::text = :uid
            """), {"uid": request.user_id}).fetchone()
        if row is None:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("User not found")
            return users_pb2.UserProfile()
        profile = users_pb2.UserProfile(
            user_id=row.user_id,
            username=row.username,
            email=row.email,
            avatar_url=row.avatar_url,
            bio=row.bio,
        )
        if row.last_seen:
            ts = timestamp_pb2.Timestamp()
            dt = row.last_seen
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            ts.FromDatetime(dt)
            profile.last_seen.CopyFrom(ts)
        return profile

    def UpdateLastSeen(self, request, context):
        dt = request.timestamp.ToDatetime(tzinfo=timezone.utc)
        with self._engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO user_profiles (user_id, last_seen)
                VALUES (:uid, :ts)
                ON CONFLICT (user_id)
                DO UPDATE SET last_seen = EXCLUDED.last_seen
            """), {"uid": request.user_id, "ts": dt})
            conn.commit()
        return common_pb2.Empty()

    def SearchUsers(self, request, context):
        limit = request.limit if request.limit > 0 else 20
        with self._engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT au.id::text AS user_id,
                       au.username,
                       COALESCE(up.avatar_url, '') AS avatar_url
                FROM auth.users au
                LEFT JOIN user_profiles up ON au.id::text = up.user_id
                WHERE au.username ILIKE :q
                LIMIT :lim
            """), {"q": f"%{request.query}%", "lim": limit}).fetchall()
        return users_pb2.SearchUsersResponse(
            users=[
                users_pb2.UserSummary(
                    user_id=r.user_id,
                    username=r.username,
                    avatar_url=r.avatar_url,
                )
                for r in rows
            ]
        )


def serve_grpc():
    engine = _get_engine()
    metadata.create_all(engine)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    users_pb2_grpc.add_UsersServiceServicer_to_server(UsersServicer(engine), server)
    server.add_insecure_port("0.0.0.0:50052")
    server.start()
    print("Users gRPC server listening on :50052", flush=True)
    server.wait_for_termination()


if __name__ == "__main__":
    # Start gRPC in a background thread
    grpc_thread = threading.Thread(target=serve_grpc, daemon=True)
    grpc_thread.start()

    # Start REST server in the main thread
    import uvicorn
    from src.rest import app
    print("Users REST server starting on :8003", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=8003)
