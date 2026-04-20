import uuid
import pytest
import grpc
from unittest.mock import MagicMock
from sqlalchemy import text
from generated import files_pb2
from src.main import FilesServicer


@pytest.fixture
def servicer(engine):
    return FilesServicer(engine)


@pytest.fixture
def seed_file(conn):
    fid = str(uuid.uuid4())
    conn.execute(text("""
        INSERT INTO files (id, owner_id, url, mime_type, size)
        VALUES (:id, :owner, :url, :mime, :size)
    """), {"id": fid, "owner": "user-1", "url": f"http://files:8002/files/{fid}.jpg", "mime": "image/jpeg", "size": 12345})
    conn.commit()
    yield fid
    conn.execute(text("DELETE FROM files WHERE id = :id"), {"id": fid})
    conn.commit()


def test_get_file_metadata_found(servicer, seed_file):
    req = files_pb2.GetFileMetadataRequest(file_id=seed_file)
    ctx = MagicMock()
    resp = servicer.GetFileMetadata(req, ctx)
    assert resp.id == seed_file
    assert resp.owner_id == "user-1"
    assert resp.mime_type == "image/jpeg"
    assert resp.size == 12345


def test_get_file_metadata_not_found(servicer):
    req = files_pb2.GetFileMetadataRequest(file_id=str(uuid.uuid4()))
    ctx = MagicMock()
    servicer.GetFileMetadata(req, ctx)
    ctx.set_code.assert_called_with(grpc.StatusCode.NOT_FOUND)
