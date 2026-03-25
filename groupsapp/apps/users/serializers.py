from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class PublicUserSerializer(serializers.ModelSerializer):
    """Datos públicos de un usuario (para terceros)."""

    class Meta:
        model = User
        fields = ["id", "username", "avatar", "bio", "last_seen"]
        read_only_fields = fields


class PrivateUserSerializer(serializers.ModelSerializer):
    """Datos completos del usuario autenticado (solo /me)."""

    class Meta:
        model = User
        fields = ["id", "username", "email", "avatar", "bio", "last_seen", "created_at"]
        read_only_fields = ["id", "email", "created_at", "last_seen"]


class UpdateMeSerializer(serializers.ModelSerializer):
    """Permite actualizar username, bio y avatar."""

    username = serializers.CharField(max_length=150, required=False)
    bio = serializers.CharField(allow_blank=True, required=False)
    avatar = serializers.ImageField(required=False)

    class Meta:
        model = User
        fields = ["username", "bio", "avatar"]

    def validate_username(self, value):
        user = self.context["request"].user
        if (
            User.objects.filter(username__iexact=value)
            .exclude(pk=user.pk)
            .exists()
        ):
            raise serializers.ValidationError("This username is already taken.")
        return value
