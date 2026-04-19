import sys
import os
import uuid
from concurrent import futures
from datetime import timezone

import grpc
from google.protobuf import timestamp_pb2
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from generated import groups_pb2, groups_pb2_grpc, common_pb2
from src.db import get_engine
from src.models import metadata

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = get_engine()
    return _engine


def _ts_from_row(dt) -> timestamp_pb2.Timestamp:
    ts = timestamp_pb2.Timestamp()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    ts.FromDatetime(dt)
    return ts


def _row_to_group(row) -> groups_pb2.Group:
    g = groups_pb2.Group(
        id=row.id,
        name=row.name,
        description=row.description,
        owner_id=row.owner_id,
        subscription_type=row.subscription_type,
        avatar_url=row.avatar_url,
    )
    if row.created_at:
        g.created_at.CopyFrom(_ts_from_row(row.created_at))
    return g


def _row_to_channel(row) -> groups_pb2.Channel:
    ch = groups_pb2.Channel(
        id=row.id,
        group_id=row.group_id,
        name=row.name,
        description=row.description,
    )
    if row.created_at:
        ch.created_at.CopyFrom(_ts_from_row(row.created_at))
    return ch


class GroupsServicer(groups_pb2_grpc.GroupsServiceServicer):
    def __init__(self, engine=None):
        self._engine = engine or _get_engine()

    def Healthcheck(self, request, context):
        ts = timestamp_pb2.Timestamp()
        ts.GetCurrentTime()
        return common_pb2.HealthcheckResponse(
            service="groups", status="OK", checked_at=ts
        )

    # ── Group CRUD ────────────────────────────────────────────────────────────

    def CreateGroup(self, request, context):
        group_id = str(uuid.uuid4())
        with self._engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO groups (id, name, description, owner_id, subscription_type)
                VALUES (:id, :name, :desc, :owner, :sub)
            """), {
                "id": group_id, "name": request.name,
                "desc": request.description, "owner": request.owner_id,
                "sub": request.subscription_type or "free",
            })
            conn.execute(text("""
                INSERT INTO group_members (user_id, group_id, role)
                VALUES (:uid, :gid, 'owner')
            """), {"uid": request.owner_id, "gid": group_id})
            conn.commit()
            row = conn.execute(
                text("SELECT * FROM groups WHERE id = :id"), {"id": group_id}
            ).fetchone()
        return _row_to_group(row)

    def GetGroup(self, request, context):
        with self._engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM groups WHERE id = :id"), {"id": request.group_id}
            ).fetchone()
        if row is None:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Group not found")
            return groups_pb2.Group()
        return _row_to_group(row)

    def UpdateGroup(self, request, context):
        with self._engine.connect() as conn:
            row = conn.execute(text("""
                UPDATE groups
                SET name = :name, description = :desc, subscription_type = :sub
                WHERE id = :id
                RETURNING *
            """), {
                "id": request.group_id, "name": request.name,
                "desc": request.description, "sub": request.subscription_type,
            }).fetchone()
            conn.commit()
        if row is None:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Group not found")
            return groups_pb2.Group()
        return _row_to_group(row)

    def DeleteGroup(self, request, context):
        with self._engine.connect() as conn:
            conn.execute(
                text("DELETE FROM group_members WHERE group_id = :id"),
                {"id": request.group_id},
            )
            conn.execute(
                text("DELETE FROM channels WHERE group_id = :id"),
                {"id": request.group_id},
            )
            conn.execute(
                text("DELETE FROM groups WHERE id = :id"), {"id": request.group_id}
            )
            conn.commit()
        return common_pb2.Empty()

    def ListUserGroups(self, request, context):
        with self._engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT g.id, g.name, g.avatar_url, gm.role
                FROM groups g
                JOIN group_members gm ON g.id = gm.group_id
                WHERE gm.user_id = :uid
            """), {"uid": request.user_id}).fetchall()
        return groups_pb2.UserGroupsResponse(
            groups=[
                groups_pb2.GroupSummary(
                    id=r.id, name=r.name, avatar_url=r.avatar_url, role=r.role
                )
                for r in rows
            ]
        )

    # ── Membership ────────────────────────────────────────────────────────────

    def VerifyMembership(self, request, context):
        with self._engine.connect() as conn:
            row = conn.execute(text("""
                SELECT role FROM group_members
                WHERE user_id = :uid AND group_id = :gid
            """), {"uid": request.user_id, "gid": request.group_id}).fetchone()
        if row is None:
            return groups_pb2.MembershipInfo(is_member=False, role="")
        return groups_pb2.MembershipInfo(is_member=True, role=row.role)

    def AddMember(self, request, context):
        with self._engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO group_members (user_id, group_id, role)
                VALUES (:uid, :gid, 'member')
                ON CONFLICT DO NOTHING
            """), {"uid": request.user_id, "gid": request.group_id})
            conn.commit()
        return common_pb2.Empty()

    def RemoveMember(self, request, context):
        with self._engine.connect() as conn:
            conn.execute(text("""
                DELETE FROM group_members
                WHERE user_id = :uid AND group_id = :gid
            """), {"uid": request.user_id, "gid": request.group_id})
            conn.commit()
        return common_pb2.Empty()

    def JoinGroup(self, request, context):
        with self._engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO group_members (user_id, group_id, role)
                VALUES (:uid, :gid, 'member')
                ON CONFLICT DO NOTHING
            """), {"uid": request.user_id, "gid": request.group_id})
            conn.commit()
        return common_pb2.Empty()

    def LeaveGroup(self, request, context):
        with self._engine.connect() as conn:
            conn.execute(text("""
                DELETE FROM group_members
                WHERE user_id = :uid AND group_id = :gid
            """), {"uid": request.user_id, "gid": request.group_id})
            conn.commit()
        return common_pb2.Empty()

    def ListMembers(self, request, context):
        with self._engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT user_id, role, joined_at FROM group_members
                WHERE group_id = :gid
            """), {"gid": request.group_id}).fetchall()
        members = []
        for r in rows:
            m = groups_pb2.Member(user_id=r.user_id, role=r.role)
            if r.joined_at:
                m.joined_at.CopyFrom(_ts_from_row(r.joined_at))
            members.append(m)
        return groups_pb2.MembersList(members=members)

    def ChangeRole(self, request, context):
        with self._engine.connect() as conn:
            conn.execute(text("""
                UPDATE group_members SET role = :role
                WHERE user_id = :uid AND group_id = :gid
            """), {"role": request.role, "uid": request.user_id, "gid": request.group_id})
            conn.commit()
        return common_pb2.Empty()

    # ── Channels ──────────────────────────────────────────────────────────────

    def CreateChannel(self, request, context):
        channel_id = str(uuid.uuid4())
        with self._engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO channels (id, group_id, name, description)
                VALUES (:id, :gid, :name, :desc)
            """), {
                "id": channel_id, "gid": request.group_id,
                "name": request.name, "desc": request.description,
            })
            conn.commit()
            row = conn.execute(
                text("SELECT * FROM channels WHERE id = :id"), {"id": channel_id}
            ).fetchone()
        return _row_to_channel(row)

    def ListChannels(self, request, context):
        with self._engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT * FROM channels WHERE group_id = :gid ORDER BY created_at
            """), {"gid": request.group_id}).fetchall()
        return groups_pb2.ChannelsList(channels=[_row_to_channel(r) for r in rows])

    def GetChannel(self, request, context):
        with self._engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM channels WHERE id = :id"), {"id": request.channel_id}
            ).fetchone()
        if row is None:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Channel not found")
            return groups_pb2.ChannelWithGroup()
        return groups_pb2.ChannelWithGroup(
            channel=_row_to_channel(row),
            group_id=row.group_id,
        )


def serve():
    engine = _get_engine()
    metadata.create_all(engine)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    groups_pb2_grpc.add_GroupsServiceServicer_to_server(GroupsServicer(engine), server)
    server.add_insecure_port("0.0.0.0:50053")
    server.start()
    print("Groups gRPC server listening on :50053", flush=True)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
