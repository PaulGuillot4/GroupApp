import pytest
from accounts.models import User

@pytest.mark.django_db
def test_user_model_has_uuid_pk():
    user = User.objects.create_user(
        username="alice", email="alice@example.com", password="securepass123"
    )
    assert user.pk is not None
    import uuid as uuid_module
    assert isinstance(user.pk, uuid_module.UUID)
    assert user.username == "alice"
    assert user.check_password("securepass123")
