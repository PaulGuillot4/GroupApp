from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.groups.models import Channel, Group, GroupMember
from apps.groups.permissions import IsGroupAdmin, IsGroupMember, IsGroupOwner
from apps.groups.serializers import (
    AddMemberSerializer,
    ChangeRoleSerializer,
    ChannelSerializer,
    CreateChannelSerializer,
    CreateGroupSerializer,
    GroupMemberSerializer,
    GroupSerializer,
    UpdateChannelSerializer,
    UpdateGroupSerializer,
)

User = get_user_model()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _error(code: str, message: str, details=None, http_status=status.HTTP_400_BAD_REQUEST):
    payload = {"error": {"code": code, "message": message}}
    if details is not None:
        payload["error"]["details"] = details
    return Response(payload, status=http_status)


def _get_group_or_404(group_id):
    try:
        return Group.objects.get(pk=group_id)
    except (Group.DoesNotExist, ValueError):
        return None


def _get_channel_or_404(channel_id, group):
    try:
        return Channel.objects.get(pk=channel_id, group=group)
    except (Channel.DoesNotExist, ValueError):
        return None


# ===================================================================
# GROUPS
# ===================================================================

class GroupListCreateView(APIView):
    """
    GET  /api/groups/          → list groups the user belongs to
    POST /api/groups/          → create a new group
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        group_ids = GroupMember.objects.filter(user=request.user).values_list(
            "group_id", flat=True
        )
        groups = Group.objects.filter(pk__in=group_ids).prefetch_related(
            "channels", "members"
        )
        serializer = GroupSerializer(groups, many=True)
        return Response(serializer.data)

    @transaction.atomic
    def post(self, request):
        serializer = CreateGroupSerializer(data=request.data)
        if not serializer.is_valid():
            return _error(
                code="VALIDATION_ERROR",
                message="Group creation failed due to validation errors.",
                details=serializer.errors,
            )
        group = serializer.save(owner=request.user)

        # Owner is automatically admin
        GroupMember.objects.create(group=group, user=request.user, role="admin")

        # Create default "general" channel
        Channel.objects.create(group=group, name="general")

        return Response(
            GroupSerializer(group).data,
            status=status.HTTP_201_CREATED,
        )


class GroupDetailView(APIView):
    """
    GET    /api/groups/:groupId/   → group detail (members only)
    PUT    /api/groups/:groupId/   → edit group (admin only)
    DELETE /api/groups/:groupId/   → delete group (owner only)
    """
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        if self.request.method == "GET":
            return [IsAuthenticated(), IsGroupMember()]
        if self.request.method == "PUT":
            return [IsAuthenticated(), IsGroupAdmin()]
        if self.request.method == "DELETE":
            return [IsAuthenticated(), IsGroupOwner()]
        return [IsAuthenticated()]

    def get(self, request, group_id):
        group = _get_group_or_404(group_id)
        if group is None:
            return _error(
                code="GROUP_NOT_FOUND",
                message=f"Group with id '{group_id}' does not exist.",
                http_status=status.HTTP_404_NOT_FOUND,
            )
        serializer = GroupSerializer(group)
        return Response(serializer.data)

    def put(self, request, group_id):
        group = _get_group_or_404(group_id)
        if group is None:
            return _error(
                code="GROUP_NOT_FOUND",
                message=f"Group with id '{group_id}' does not exist.",
                http_status=status.HTTP_404_NOT_FOUND,
            )
        serializer = UpdateGroupSerializer(group, data=request.data, partial=True)
        if not serializer.is_valid():
            return _error(
                code="VALIDATION_ERROR",
                message="Group update failed due to validation errors.",
                details=serializer.errors,
            )
        serializer.save()
        return Response(GroupSerializer(group).data)

    def delete(self, request, group_id):
        group = _get_group_or_404(group_id)
        if group is None:
            return _error(
                code="GROUP_NOT_FOUND",
                message=f"Group with id '{group_id}' does not exist.",
                http_status=status.HTTP_404_NOT_FOUND,
            )
        group.delete()  # cascades channels, members, messages
        return Response(
            {"message": "Group deleted successfully."},
            status=status.HTTP_200_OK,
        )


class GroupJoinView(APIView):
    """POST /api/groups/:groupId/join/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, group_id):
        group = _get_group_or_404(group_id)
        if group is None:
            return _error(
                code="GROUP_NOT_FOUND",
                message=f"Group with id '{group_id}' does not exist.",
                http_status=status.HTTP_404_NOT_FOUND,
            )

        if group.subscription_type != "open":
            return _error(
                code="JOIN_NOT_ALLOWED",
                message="This group is not open for joining. An admin must invite you.",
                http_status=status.HTTP_403_FORBIDDEN,
            )

        if GroupMember.objects.filter(group=group, user=request.user).exists():
            return _error(
                code="ALREADY_MEMBER",
                message="You are already a member of this group.",
            )

        GroupMember.objects.create(group=group, user=request.user, role="member")
        return Response(
            {"message": "Joined successfully"},
            status=status.HTTP_200_OK,
        )


class GroupLeaveView(APIView):
    """POST /api/groups/:groupId/leave/"""
    permission_classes = [IsAuthenticated, IsGroupMember]

    def post(self, request, group_id):
        group = _get_group_or_404(group_id)
        if group is None:
            return _error(
                code="GROUP_NOT_FOUND",
                message=f"Group with id '{group_id}' does not exist.",
                http_status=status.HTTP_404_NOT_FOUND,
            )

        if group.owner == request.user:
            return _error(
                code="OWNER_CANNOT_LEAVE",
                message="The owner cannot leave the group. Transfer ownership first.",
                http_status=status.HTTP_403_FORBIDDEN,
            )

        membership = GroupMember.objects.filter(
            group=group, user=request.user
        ).first()
        if membership:
            membership.delete()

        return Response(
            {"message": "Left successfully"},
            status=status.HTTP_200_OK,
        )


# ===================================================================
# MEMBERS
# ===================================================================

class MemberListCreateView(APIView):
    """
    GET  /api/groups/:groupId/members/     → list members
    POST /api/groups/:groupId/members/     → add a member (admin only)
    """

    def get_permissions(self):
        if self.request.method == "GET":
            return [IsAuthenticated(), IsGroupMember()]
        # POST → admin only
        return [IsAuthenticated(), IsGroupAdmin()]

    def get(self, request, group_id):
        group = _get_group_or_404(group_id)
        if group is None:
            return _error(
                code="GROUP_NOT_FOUND",
                message=f"Group with id '{group_id}' does not exist.",
                http_status=status.HTTP_404_NOT_FOUND,
            )
        memberships = GroupMember.objects.filter(group=group).select_related("user")
        serializer = GroupMemberSerializer(memberships, many=True)
        return Response(serializer.data)

    def post(self, request, group_id):
        group = _get_group_or_404(group_id)
        if group is None:
            return _error(
                code="GROUP_NOT_FOUND",
                message=f"Group with id '{group_id}' does not exist.",
                http_status=status.HTTP_404_NOT_FOUND,
            )
        serializer = AddMemberSerializer(data=request.data, context={"group": group})
        if not serializer.is_valid():
            return _error(
                code="VALIDATION_ERROR",
                message="Failed to add member.",
                details=serializer.errors,
            )
        user = User.objects.get(pk=serializer.validated_data["userId"])
        membership = GroupMember.objects.create(
            group=group, user=user, role="member"
        )
        return Response(
            GroupMemberSerializer(membership).data,
            status=status.HTTP_201_CREATED,
        )


class MemberRemoveView(APIView):
    """DELETE /api/groups/:groupId/members/:userId/"""
    permission_classes = [IsAuthenticated, IsGroupAdmin]

    def delete(self, request, group_id, user_id):
        group = _get_group_or_404(group_id)
        if group is None:
            return _error(
                code="GROUP_NOT_FOUND",
                message=f"Group with id '{group_id}' does not exist.",
                http_status=status.HTTP_404_NOT_FOUND,
            )

        if str(group.owner_id) == str(user_id):
            return _error(
                code="CANNOT_REMOVE_OWNER",
                message="The owner cannot be removed from the group.",
                http_status=status.HTTP_403_FORBIDDEN,
            )

        membership = GroupMember.objects.filter(
            group=group, user_id=user_id
        ).first()
        if membership is None:
            return _error(
                code="MEMBER_NOT_FOUND",
                message=f"User with id '{user_id}' is not a member of this group.",
                http_status=status.HTTP_404_NOT_FOUND,
            )

        membership.delete()
        return Response(
            {"message": "Member removed successfully."},
            status=status.HTTP_200_OK,
        )


class MemberRoleView(APIView):
    """PUT /api/groups/:groupId/members/:userId/role/"""
    permission_classes = [IsAuthenticated, IsGroupOwner]

    def put(self, request, group_id, user_id):
        group = _get_group_or_404(group_id)
        if group is None:
            return _error(
                code="GROUP_NOT_FOUND",
                message=f"Group with id '{group_id}' does not exist.",
                http_status=status.HTTP_404_NOT_FOUND,
            )

        membership = GroupMember.objects.filter(
            group=group, user_id=user_id
        ).first()
        if membership is None:
            return _error(
                code="MEMBER_NOT_FOUND",
                message=f"User with id '{user_id}' is not a member of this group.",
                http_status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ChangeRoleSerializer(data=request.data)
        if not serializer.is_valid():
            return _error(
                code="VALIDATION_ERROR",
                message="Invalid role.",
                details=serializer.errors,
            )

        membership.role = serializer.validated_data["role"]
        membership.save(update_fields=["role"])
        return Response(GroupMemberSerializer(membership).data)


# ===================================================================
# CHANNELS
# ===================================================================

class ChannelListCreateView(APIView):
    """
    GET  /api/groups/:groupId/channels/     → list channels (member)
    POST /api/groups/:groupId/channels/     → create channel (admin)
    """

    def get_permissions(self):
        if self.request.method == "GET":
            return [IsAuthenticated(), IsGroupMember()]
        return [IsAuthenticated(), IsGroupAdmin()]

    def get(self, request, group_id):
        group = _get_group_or_404(group_id)
        if group is None:
            return _error(
                code="GROUP_NOT_FOUND",
                message=f"Group with id '{group_id}' does not exist.",
                http_status=status.HTTP_404_NOT_FOUND,
            )
        channels = Channel.objects.filter(group=group)
        serializer = ChannelSerializer(channels, many=True)
        return Response(serializer.data)

    def post(self, request, group_id):
        group = _get_group_or_404(group_id)
        if group is None:
            return _error(
                code="GROUP_NOT_FOUND",
                message=f"Group with id '{group_id}' does not exist.",
                http_status=status.HTTP_404_NOT_FOUND,
            )
        serializer = CreateChannelSerializer(
            data=request.data, context={"group": group}
        )
        if not serializer.is_valid():
            return _error(
                code="VALIDATION_ERROR",
                message="Channel creation failed due to validation errors.",
                details=serializer.errors,
            )
        channel = serializer.save(group=group)
        return Response(
            ChannelSerializer(channel).data,
            status=status.HTTP_201_CREATED,
        )


class ChannelDetailView(APIView):
    """
    PUT    /api/groups/:groupId/channels/:channelId/   → edit (admin)
    DELETE /api/groups/:groupId/channels/:channelId/   → delete (admin, not general)
    """
    permission_classes = [IsAuthenticated, IsGroupAdmin]

    def put(self, request, group_id, channel_id):
        group = _get_group_or_404(group_id)
        if group is None:
            return _error(
                code="GROUP_NOT_FOUND",
                message=f"Group with id '{group_id}' does not exist.",
                http_status=status.HTTP_404_NOT_FOUND,
            )
        channel = _get_channel_or_404(channel_id, group)
        if channel is None:
            return _error(
                code="CHANNEL_NOT_FOUND",
                message=f"Channel with id '{channel_id}' does not exist in this group.",
                http_status=status.HTTP_404_NOT_FOUND,
            )
        serializer = UpdateChannelSerializer(channel, data=request.data, partial=True)
        if not serializer.is_valid():
            return _error(
                code="VALIDATION_ERROR",
                message="Channel update failed due to validation errors.",
                details=serializer.errors,
            )
        serializer.save()
        return Response(ChannelSerializer(channel).data)

    def delete(self, request, group_id, channel_id):
        group = _get_group_or_404(group_id)
        if group is None:
            return _error(
                code="GROUP_NOT_FOUND",
                message=f"Group with id '{group_id}' does not exist.",
                http_status=status.HTTP_404_NOT_FOUND,
            )
        channel = _get_channel_or_404(channel_id, group)
        if channel is None:
            return _error(
                code="CHANNEL_NOT_FOUND",
                message=f"Channel with id '{channel_id}' does not exist in this group.",
                http_status=status.HTTP_404_NOT_FOUND,
            )

        if channel.name.lower() == "general":
            return _error(
                code="CANNOT_DELETE_GENERAL",
                message="The 'general' channel cannot be deleted.",
                http_status=status.HTTP_403_FORBIDDEN,
            )

        channel.delete()
        return Response(
            {"message": "Channel deleted successfully."},
            status=status.HTTP_200_OK,
        )
