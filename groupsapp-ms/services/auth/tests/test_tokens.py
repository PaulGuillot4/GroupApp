import pytest
from accounts.models import User
from accounts.tokens import CustomRefreshToken


@pytest.mark.django_db
def test_refresh_token_embeds_username():
    user = User.objects.create_user(
        username="bob", email="bob@example.com", password="pass123"
    )
    refresh = CustomRefreshToken.for_user(user)
    assert refresh["username"] == "bob"
    assert "user_id" in refresh.payload


@pytest.mark.django_db
def test_access_token_from_refresh_contains_username():
    user = User.objects.create_user(
        username="carol", email="carol@example.com", password="pass123"
    )
    refresh = CustomRefreshToken.for_user(user)
    access = refresh.access_token
    assert access["username"] == "carol"
