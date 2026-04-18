from rest_framework_simplejwt.tokens import RefreshToken as BaseRefreshToken


class CustomRefreshToken(BaseRefreshToken):
    @classmethod
    def for_user(cls, user):
        token = super().for_user(user)
        token["username"] = user.username
        return token
