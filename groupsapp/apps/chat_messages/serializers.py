from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.chat_messages.models import Message, MessageStatus

User = get_user_model()


class _SenderSerializer(serializers.ModelSerializer):
    """Minimal user info embedded in messages."""

    class Meta:
        model = User
        fields = ["id", "username", "avatar"]
        read_only_fields = fields


class MessageStatusSerializer(serializers.ModelSerializer):
    user = _SenderSerializer(read_only=True)

    class Meta:
        model = MessageStatus
        fields = ["user", "status", "updated_at"]
        read_only_fields = fields


class MessageSerializer(serializers.ModelSerializer):
    sender = _SenderSerializer(read_only=True)
    statuses = MessageStatusSerializer(many=True, read_only=True)

    class Meta:
        model = Message
        fields = [
            "id",
            "sender",
            "type",
            "group",
            "channel",
            "receiver",
            "content",
            "message_type",
            "file_url",
            "created_at",
            "statuses",
        ]
        read_only_fields = fields
