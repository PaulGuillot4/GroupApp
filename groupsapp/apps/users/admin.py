from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "last_seen", "is_staff", "created_at")
    list_filter = ("is_staff", "is_superuser", "is_active")
    search_fields = ("username", "email")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Profile", {"fields": ("avatar", "bio", "last_seen")}),
    )
