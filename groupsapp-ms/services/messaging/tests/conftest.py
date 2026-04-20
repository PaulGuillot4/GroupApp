import pytest


@pytest.fixture
def make_message(db):
    from chat.models import Message

    def _make(**kwargs):
        defaults = {
            "sender_id": "user-a",
            "type": "group",
            "group_id": "grp-1",
            "channel_id": "",
            "receiver_id": "",
            "content": "hello",
            "message_type": "text",
            "file_url": "",
        }
        defaults.update(kwargs)
        return Message.objects.create(**defaults)

    return _make
