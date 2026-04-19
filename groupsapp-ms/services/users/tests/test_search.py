import uuid
import pytest
from unittest.mock import MagicMock
from sqlalchemy import text
from generated import users_pb2
from src.main import UsersServicer


@pytest.fixture
def servicer(engine):
    return UsersServicer(engine)


@pytest.fixture
def seed_searchable_users(conn):
    uids = []
    for username in ["alice_srch", "bob_srch"]:
        uid = str(uuid.uuid4())
        conn.execute(text("""
            INSERT INTO auth.users
              (id, password, is_superuser, username, first_name, last_name, email,
               is_staff, is_active, date_joined)
            VALUES (:id, 'hashed!', false, :username, '', '', :email, false, true, now())
            ON CONFLICT DO NOTHING
        """), {"id": uid, "username": username, "email": f"{username}@test.com"})
        uids.append(uid)
    conn.commit()
    yield uids
    for uid in uids:
        conn.execute(text("DELETE FROM auth.users WHERE id::text = :uid"), {"uid": uid})
    conn.commit()


def test_search_finds_matching(servicer, seed_searchable_users):
    req = users_pb2.SearchUsersRequest(query="alice", limit=10)
    ctx = MagicMock()
    resp = servicer.SearchUsers(req, ctx)
    usernames = [u.username for u in resp.users]
    assert "alice_srch" in usernames
    assert "bob_srch" not in usernames


def test_search_limit(servicer, seed_searchable_users):
    req = users_pb2.SearchUsersRequest(query="_srch", limit=1)
    ctx = MagicMock()
    resp = servicer.SearchUsers(req, ctx)
    assert len(resp.users) <= 1


def test_search_no_results(servicer):
    req = users_pb2.SearchUsersRequest(query="zzznomatch99xyz", limit=10)
    ctx = MagicMock()
    resp = servicer.SearchUsers(req, ctx)
    assert list(resp.users) == []


def test_search_returns_avatar_url(servicer, seed_searchable_users, conn):
    uid = seed_searchable_users[0]
    conn.execute(text("""
        INSERT INTO user_profiles (user_id, avatar_url, bio)
        VALUES (:uid, 'http://cdn.example.com/a.jpg', '')
        ON CONFLICT (user_id) DO UPDATE SET avatar_url = EXCLUDED.avatar_url
    """), {"uid": uid})
    conn.commit()
    req = users_pb2.SearchUsersRequest(query="alice_srch", limit=10)
    ctx = MagicMock()
    resp = servicer.SearchUsers(req, ctx)
    assert len(resp.users) == 1
    assert resp.users[0].avatar_url == "http://cdn.example.com/a.jpg"
