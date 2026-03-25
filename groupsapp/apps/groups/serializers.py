from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.groups.models import Channel, Group, GroupMember

User = get_user_model()


# ------------------------------------------------------------------
# Nested helpers
# ------------------------------------------------------------------

class _MemberUserSerializer(serializers.ModelSerializer):
    """Minimal user representation nested inside GroupMemberSerializer."""

    class Meta:
        model = User
        fields = ["id", "username", "avatar", "last_seen"]
        read_only_fields = fields


# ------------------------------------------------------------------
# Channel
# ------------------------------------------------------------------

class ChannelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Channel
        fields = ["id", "name", "description", "group", "created_at"]
        read_only_fields = ["id", "group", "created_at"]


class CreateChannelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Channel
        fields = ["name", "description"]

    def validate_name(self, value):
        group = self.context.get("group")
        if group and Channel.objects.filter(group=group, name__iexact=value).exists():
            raise serializers.ValidationError(
                "A channel with this name already exists in the group."
            )
        return value


class UpdateChannelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Channel
        fields = ["name", "description"]

    def validate_name(self, value):
        group = self.instance.group if self.instance else None
        qs = Channel.objects.filter(group=group, name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "A channel with this name already exists in the group."
            )
        return value


# ------------------------------------------------------------------
# Group member
# ------------------------------------------------------------------

class GroupMemberSerializer(serializers.ModelSerializer):
    user = _MemberUserSerializer(read_only=True)

    class Meta:
        model = GroupMember
        fields = ["user", "role", "joined_at"]
        read_only_fields = fields


class AddMemberSerializer(serializers.Serializer):
    userId = serializers.IntegerField()

    def validate_userId(self, value):
        if not User.objects.filter(pk=value).exists():
            raise serializers.ValidationError("User does not exist.")
        group = self.context.get("group")
        if group and GroupMember.objects.filter(group=group, user_id=value).exists():
            raise serializers.ValidationError(
                "User is already a member of this group."
            )
        return value


class ChangeRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=["admin", "member"])


# ------------------------------------------------------------------
# Group
# ------------------------------------------------------------------

class GroupSerializer(serializers.ModelSerializer):
    member_count = serializers.SerializerMethodField()
    channels = ChannelSerializer(many=True, read_only=True)

    class Meta:
        model = Group
        fields = [
            "id",
            "name",
            "description",
            "avatar",
            "owner",
            "subscription_type",
            "member_count",
            "channels",
            "created_at",
        ]
        read_only_fields = ["id", "owner", "member_count", "channels", "created_at"]

    def get_member_count(self, obj):
        return obj.members.count()


class CreateGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ["name", "description", "avatar", "subscription_type"]

    def validate_subscription_type(self, value):
        valid = [c[0] for c in Group.SUBSCRIPTION_CHOICES]
        if value not in valid:
            raise serializers.ValidationError(
                f"Invalid subscription type. Choose from: {', '.join(valid)}"
            )
        return value


class UpdateGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ["name", "description", "avatar", "subscription_type"]

    def validate_subscription_type(self, value):
        valid = [c[0] for c in Group.SUBSCRIPTION_CHOICES]
        if value not in valid:
            raise serializers.ValidationError(
                f"Invalid subscription type. Choose from: {', '.join(valid)}"
            )
        return value
