import uuid

from django.conf import settings
from django.db import models


class Group(models.Model):
    """A group that users can join to communicate."""

    SUBSCRIPTION_CHOICES = [
        ("open", "Open"),
        ("invite_only", "Invite Only"),
        ("private", "Private"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    avatar = models.ImageField(upload_to="groups/", null=True, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_groups",
    )
    subscription_type = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_CHOICES,
        default="open",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "groups"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class Channel(models.Model):
    """A channel within a group."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="channels",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "channels"
        ordering = ["-created_at"]

    def __str__(self):
        return f"#{self.name} ({self.group.name})"


class GroupMember(models.Model):
    """Membership relationship between a user and a group."""

    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("member", "Member"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="group_memberships",
    )
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="members",
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="member")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "group_members"
        unique_together = ("user", "group")

    def __str__(self):
        return f"{self.user.username} → {self.group.name} ({self.role})"
