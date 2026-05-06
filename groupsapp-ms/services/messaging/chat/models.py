import uuid
from django.db import models


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sender_id = models.CharField(max_length=36)
    sender_username = models.CharField(max_length=150, blank=True, default="")
    type = models.CharField(max_length=20)
    group_id = models.CharField(max_length=36, blank=True, default="")
    channel_id = models.CharField(max_length=36, blank=True, default="")
    receiver_id = models.CharField(max_length=36, blank=True, default="")
    content = models.TextField(blank=True, default="")
    message_type = models.CharField(max_length=20, default="text")
    file_url = models.CharField(max_length=512, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "chat"
        ordering = ["-created_at"]


class MessageStatus(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="statuses")
    user_id = models.CharField(max_length=36)
    status = models.CharField(max_length=20, default="sent")  # sent | delivered | read
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "chat"
        unique_together = [("message", "user_id")]
