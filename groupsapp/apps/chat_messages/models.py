import uuid

from django.conf import settings
from django.db import models


class Message(models.Model):
    """A message sent in a group, channel, or private conversation."""

    TYPE_CHOICES = [
        ("group", "Group"),
        ("channel", "Channel"),
        ("private", "Private"),
    ]

    MESSAGE_TYPE_CHOICES = [
        ("text", "Text"),
        ("file", "File"),
        ("image", "Image"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages",
        db_index=True,
    )
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, db_index=True)
    group = models.ForeignKey(
        "groups.Group",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="messages",
        db_index=True,
    )
    channel = models.ForeignKey(
        "groups.Channel",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="messages",
        db_index=True,
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="received_messages",
        db_index=True,
    )
    content = models.TextField(blank=True)
    message_type = models.CharField(
        max_length=10,
        choices=MESSAGE_TYPE_CHOICES,
        default="text",
    )
    file_url = models.CharField(max_length=500, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "messages"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.sender.username}: {self.content[:50] or '[file]'}"


class MessageStatus(models.Model):
    """Delivery / read status of a message for a specific user."""

    STATUS_CHOICES = [
        ("sent", "Sent"),
        ("delivered", "Delivered"),
        ("read", "Read"),
    ]

    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name="statuses",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="message_statuses",
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="sent")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "message_statuses"
        unique_together = ("message", "user")

    def __str__(self):
        return f"{self.message_id} → {self.user.username}: {self.status}"
