import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user model for GroupsApp."""

    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)
    bio = models.TextField(blank=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "users"
        ordering = ["-created_at"]

    def __str__(self):
        return self.username
