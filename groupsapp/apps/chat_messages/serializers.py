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
    status = serializers.SerializerMethodField()

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
            "status",
        ]
        read_only_fields = fields

    def get_status(self, obj):
        """
        Return the 'best' status for this message from the perspective of the sender.
        For private: sender wants to see if receiver read it.
        For group: show 'read' if anyone read, or 'delivered' if anyone got it.
        """
        statuses = obj.statuses.all()
        if not statuses:
            return "sent"
        
        # For private messages, we look for the status of the receiver specifically
        if obj.type == "private" and obj.receiver_id:
            receiver_status = statuses.filter(user_id=obj.receiver_id).first()
            return receiver_status.status if receiver_status else "sent"
            
        # Simplified for group/channel: return the 'highest' status present
        # (read > delivered > sent)
        prio = {"read": 3, "delivered": 2, "sent": 1}
        best = "sent"
        for s in statuses:
            if prio.get(s.status, 0) > prio.get(best, 0):
                best = s.status
        return best
