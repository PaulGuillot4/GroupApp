import os
import pytest
import mongomock

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "messaging_service.settings")

# Override channel layer to in-memory for tests
os.environ["REDIS_URL"] = ""  # forces fallback


@pytest.fixture(autouse=True)
def mock_mongo(monkeypatch):
    """Replace Motor and PyMongo clients with mongomock for all tests."""
    client = mongomock.MongoClient()
    test_db = client["test_messages"]

    import db as db_module
    monkeypatch.setattr(db_module, "_motor_client", None)
    monkeypatch.setattr(db_module, "_pymongo_client", None)
    monkeypatch.setattr(db_module, "get_sync_db", lambda: test_db)

    # For async (Motor) tests, use sync mongomock wrapped in async-compatible way
    monkeypatch.setattr(db_module, "get_async_db", lambda: test_db)

    yield test_db

    client.close()


@pytest.fixture
def make_message(mock_mongo):
    """Insert a message document directly into the mock MongoDB."""
    def _make(**kwargs):
        from repository import _msg_doc
        defaults = {
            "sender_id": "user-a",
            "sender_username": "userA",
            "type": "group",
            "group_id": "grp-1",
            "channel_id": "",
            "receiver_id": "",
            "content": "hello",
            "message_type": "text",
            "file_url": "",
        }
        defaults.update(kwargs)
        doc = _msg_doc(defaults)
        mock_mongo.messages.insert_one(doc)
        return doc

    return _make
