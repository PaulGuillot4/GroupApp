from django.contrib import admin

from .models import Channel, Group, GroupMember


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "subscription_type", "created_at")
    list_filter = ("subscription_type",)
    search_fields = ("name", "description")


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ("name", "group", "created_at")
    search_fields = ("name",)


@admin.register(GroupMember)
class GroupMemberAdmin(admin.ModelAdmin):
    list_display = ("user", "group", "role", "joined_at")
    list_filter = ("role",)
