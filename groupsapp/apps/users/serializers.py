from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()


class PrivateUserSerializer(serializers.ModelSerializer):
    """Serializer for the authenticated user's own profile."""

    class Meta:
        model = User
        fields = ["id", "username", "email", "avatar", "bio", "last_seen", "created_at"]
        read_only_fields = ["id", "created_at"]
