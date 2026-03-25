from django.contrib import admin

from .models import Message, MessageStatus


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("sender", "type", "message_type", "group", "channel", "created_at")
    list_filter = ("type", "message_type")
    search_fields = ("content",)


@admin.register(MessageStatus)
class MessageStatusAdmin(admin.ModelAdmin):
    list_display = ("message", "user", "status", "updated_at")
    list_filter = ("status",)
