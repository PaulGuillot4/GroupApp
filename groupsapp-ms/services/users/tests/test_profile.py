import uuid
import pytest
from unittest.mock import MagicMock
from sqlalchemy import text
from google.protobuf.timestamp_pb2 import Timestamp
from generated import users_pb2, common_pb2
from src.main import UsersServicer


@pytest.fixture
def servicer(engine):
    return UsersServicer(engine)


@pytest.fixture
def seed_user(conn):
    uid = str(uuid.uuid4())
    conn.execute(text("""
        INSERT INTO auth.users
          (id, password, is_superuser, username, first_name, last_name, email,
           is_staff, is_active, date_joined)
        VALUES (:id, 'hashed!', false, :username, '', '', :email, false, true, now())
        ON CONFLICT DO NOTHING
    """), {"id": uid, "username": "profileuser", "email": "profile@test.com"})
    conn.execute(text("""
        INSERT INTO user_profiles (user_id, avatar_url, bio)
        VALUES (:uid, 'http://example.com/avatar.jpg', 'A bio')
        ON CONFLICT DO NOTHING
    """), {"uid": uid})
    conn.commit()
    yield uid
    conn.execute(text("DELETE FROM user_profiles WHERE user_id = :uid"), {"uid": uid})
    conn.execute(text("DELETE FROM auth.users WHERE id::text = :uid"), {"uid": uid})
    conn.commit()


def test_get_profile_found(servicer, seed_user):
    req = users_pb2.GetProfileRequest(user_id=seed_user)
    ctx = MagicMock()
    resp = servicer.GetProfile(req, ctx)
    assert resp.user_id == seed_user
    assert resp.username == "profileuser"
    assert resp.email == "profile@test.com"
    assert resp.avatar_url == "http://example.com/avatar.jpg"
    assert resp.bio == "A bio"


def test_get_profile_not_found(servicer):
    req = users_pb2.GetProfileRequest(user_id=str(uuid.uuid4()))
    ctx = MagicMock()
    servicer.GetProfile(req, ctx)
    import grpc
    ctx.set_code.assert_called_with(grpc.StatusCode.NOT_FOUND)


def test_get_profile_no_profile_record(servicer, conn):
    uid = str(uuid.uuid4())
    conn.execute(text("""
        INSERT INTO auth.users
          (id, password, is_superuser, username, first_name, last_name, email,
           is_staff, is_active, date_joined)
        VALUES (:id, 'hashed!', false, :username, '', '', :email, false, true, now())
        ON CONFLICT DO NOTHING
    """), {"id": uid, "username": "noprofile", "email": "noprofile@test.com"})
    conn.commit()
    req = users_pb2.GetProfileRequest(user_id=uid)
    ctx = MagicMock()
    resp = servicer.GetProfile(req, ctx)
    assert resp.user_id == uid
    assert resp.username == "noprofile"
    assert resp.avatar_url == ""
    conn.execute(text("DELETE FROM auth.users WHERE id::text = :uid"), {"uid": uid})
    conn.commit()


def test_update_last_seen(servicer, seed_user):
    ts = Timestamp()
    ts.GetCurrentTime()
    req = users_pb2.UpdateLastSeenRequest(user_id=seed_user, timestamp=ts)
    ctx = MagicMock()
    resp = servicer.UpdateLastSeen(req, ctx)
    assert resp == common_pb2.Empty()
