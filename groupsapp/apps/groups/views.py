"""
Group, member, and channel views.

Each view class follows the Single Responsibility Principle:
 - Validate input via serializers
 - Delegate business logic to ``apps.groups.services``
 - Return standardised responses via ``apps.core.responses``
"""

from __future__ import annotations

from typing import Optional

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.responses import api_error_response
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
from apps.groups.services import GroupService, MembershipService

User = get_user_model()


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

    def get(self, request: Request) -> Response:
        group_ids = GroupMember.objects.filter(user=request.user).values_list(
            "group_id", flat=True
        )
        groups = Group.objects.filter(pk__in=group_ids).prefetch_related(
            "channels", "members"
        )
        return Response(GroupSerializer(groups, many=True).data)

    def post(self, request: Request) -> Response:
        serializer = CreateGroupSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error_response(
                code="VALIDATION_ERROR",
                message="Group creation failed due to validation errors.",
                details=serializer.errors,
            )

        initial_members = serializer.validated_data.pop("initial_members", [])
        validated = serializer.validated_data

        group = GroupService.create_group(
            owner=request.user,
            name=validated["name"],
            description=validated.get("description", ""),
            avatar=validated.get("avatar"),
            subscription_type=validated.get("subscription_type", "open"),
            initial_member_ids=initial_members,
        )

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

    def get(self, request: Request, group_id: str) -> Response:
        group: Optional[Group] = MembershipService.get_group_or_none(group_id)
        if group is None:
            return api_error_response(
                code="GROUP_NOT_FOUND",
                message=f"Group with id '{group_id}' does not exist.",
                http_status=status.HTTP_404_NOT_FOUND,
            )
        return Response(GroupSerializer(group).data)

    def put(self, request: Request, group_id: str) -> Response:
        group: Optional[Group] = MembershipService.get_group_or_none(group_id)
        if group is None:
            return api_error_response(
                code="GROUP_NOT_FOUND",
                message=f"Group with id '{group_id}' does not exist.",
                http_status=status.HTTP_404_NOT_FOUND,
            )
        serializer = UpdateGroupSerializer(group, data=request.data, partial=True)
        if not serializer.is_valid():
            return api_error_response(
                code="VALIDATION_ERROR",
                message="Group update failed due to validation errors.",
                details=serializer.errors,
            )
        serializer.save()
        return Response(GroupSerializer(group).data)

    def delete(self, request: Request, group_id: str) -> Response:
        group: Optional[Group] = MembershipService.get_group_or_none(group_id)
        if group is None:
            return api_error_response(
                code="GROUP_NOT_FOUND",
                message=f"Group with id '{group_id}' does not exist.",
                http_status=status.HTTP_404_NOT_FOUND,
            )
        group.delete()
        return Response(
            {"message": "Group deleted successfully."},
            status=status.HTTP_200_OK,
        )


class GroupJoinView(APIView):
    """POST /api/groups/:groupId/join/"""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, group_id: str) -> Response:
        group: Optional[Group] = MembershipService.get_group_or_none(group_id)
        if group is None:
            return api_error_response(
                code="GROUP_NOT_FOUND",
                message=f"Group with id '{group_id}' does not exist.",
                http_status=status.HTTP_404_NOT_FOUND,
            )

        if group.subscription_type != "open":
            return api_error_response(
                code="JOIN_NOT_ALLOWED",
                message="This group is not open for joining. An admin must invite you.",
                http_status=status.HTTP_403_FORBIDDEN,
            )

        if GroupMember.objects.filter(group=group, user=request.user).exists():
            return api_error_response(
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

    def post(self, request: Request, group_id: str) -> Response:
        group: Optional[Group] = MembershipService.get_group_or_none(group_id)
        if group is None:
            return api_error_response(
                code="GROUP_NOT_FOUND",
                message=f"Group with id '{group_id}' does not exist.",
                http_status=status.HTTP_404_NOT_FOUND,
            )

        if group.owner == request.user:
            return api_error_response(
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
        return [IsAuthenticated(), IsGroupAdmin()]

    def get(self, request: Request, group_id: str) -> Response:
        group: Optional[Group] = MembershipService.get_group_or_none(group_id)
        if group is None:
            return api_error_response(
                code="GROUP_NOT_FOUND",
                message=f"Group with id '{group_id}' does not exist.",
                http_status=status.HTTP_404_NOT_FOUND,
            )
        memberships = GroupMember.objects.filter(group=group).select_related("user")
        return Response(GroupMemberSerializer(memberships, many=True).data)

    def post(self, request: Request, group_id: str) -> Response:
        group: Optional[Group] = MembershipService.get_group_or_none(group_id)
        if group is None:
            return api_error_response(
                code="GROUP_NOT_FOUND",
                message=f"Group with id '{group_id}' does not exist.",
                http_status=status.HTTP_404_NOT_FOUND,
            )
        serializer = AddMemberSerializer(data=request.data, context={"group": group})
        if not serializer.is_valid():
            return api_error_response(
                code="VALIDATION_ERROR",
                message="Failed to add member.",
                details=serializer.errors,
            )
        membership = MembershipService.add_member(
            group=group,
            user_id=serializer.validated_data["userId"],
        )
        return Response(
            GroupMemberSerializer(membership).data,
            status=status.HTTP_201_CREATED,
        )


class MemberRemoveView(APIView):
    """DELETE /api/groups/:groupId/members/:userId/"""

    permission_classes = [IsAuthenticated, IsGroupAdmin]

    def delete(self, request: Request, group_id: str, user_id: int) -> Response:
        group: Optional[Group] = MembershipService.get_group_or_none(group_id)
        if group is None:
            return api_error_response(
                code="GROUP_NOT_FOUND",
                message=f"Group with id '{group_id}' does not exist.",
                http_status=status.HTTP_404_NOT_FOUND,
            )

        if str(group.owner_id) == str(user_id):
            return api_error_response(
                code="CANNOT_REMOVE_OWNER",
                message="The owner cannot be removed from the group.",
                http_status=status.HTTP_403_FORBIDDEN,
            )

        membership = GroupMember.objects.filter(
            group=group, user_id=user_id
        ).first()
        if membership is None:
            return api_error_response(
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

    def put(self, request: Request, group_id: str, user_id: int) -> Response:
        group: Optional[Group] = MembershipService.get_group_or_none(group_id)
        if group is None:
            return api_error_response(
                code="GROUP_NOT_FOUND",
                message=f"Group with id '{group_id}' does not exist.",
                http_status=status.HTTP_404_NOT_FOUND,
            )

        membership = GroupMember.objects.filter(
            group=group, user_id=user_id
        ).first()
        if membership is None:
            return api_error_response(
                code="MEMBER_NOT_FOUND",
                message=f"User with id '{user_id}' is not a member of this group.",
                http_status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ChangeRoleSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error_response(
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

    def get(self, request: Request, group_id: str) -> Response:
        group: Optional[Group] = MembershipService.get_group_or_none(group_id)
        if group is None:
            return api_error_response(
                code="GROUP_NOT_FOUND",
                message=f"Group with id '{group_id}' does not exist.",
                http_status=status.HTTP_404_NOT_FOUND,
            )
        channels = Channel.objects.filter(group=group)
        return Response(ChannelSerializer(channels, many=True).data)

    def post(self, request: Request, group_id: str) -> Response:
        group: Optional[Group] = MembershipService.get_group_or_none(group_id)
        if group is None:
            return api_error_response(
                code="GROUP_NOT_FOUND",
                message=f"Group with id '{group_id}' does not exist.",
                http_status=status.HTTP_404_NOT_FOUND,
            )
        serializer = CreateChannelSerializer(
            data=request.data, context={"group": group}
        )
        if not serializer.is_valid():
            return api_error_response(
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

    def put(self, request: Request, group_id: str, channel_id: str) -> Response:
        group: Optional[Group] = MembershipService.get_group_or_none(group_id)
        if group is None:
            return api_error_response(
                code="GROUP_NOT_FOUND",
                message=f"Group with id '{group_id}' does not exist.",
                http_status=status.HTTP_404_NOT_FOUND,
            )
        channel: Optional[Channel] = MembershipService.get_channel_or_none(
            channel_id, group
        )
        if channel is None:
            return api_error_response(
                code="CHANNEL_NOT_FOUND",
                message=f"Channel with id '{channel_id}' does not exist in this group.",
                http_status=status.HTTP_404_NOT_FOUND,
            )
        serializer = UpdateChannelSerializer(channel, data=request.data, partial=True)
        if not serializer.is_valid():
            return api_error_response(
                code="VALIDATION_ERROR",
                message="Channel update failed due to validation errors.",
                details=serializer.errors,
            )
        serializer.save()
        return Response(ChannelSerializer(channel).data)

    def delete(self, request: Request, group_id: str, channel_id: str) -> Response:
        group: Optional[Group] = MembershipService.get_group_or_none(group_id)
        if group is None:
            return api_error_response(
                code="GROUP_NOT_FOUND",
                message=f"Group with id '{group_id}' does not exist.",
                http_status=status.HTTP_404_NOT_FOUND,
            )
        channel: Optional[Channel] = MembershipService.get_channel_or_none(
            channel_id, group
        )
        if channel is None:
            return api_error_response(
                code="CHANNEL_NOT_FOUND",
                message=f"Channel with id '{channel_id}' does not exist in this group.",
                http_status=status.HTTP_404_NOT_FOUND,
            )

        if channel.name.lower() == "general":
            return api_error_response(
                code="CANNOT_DELETE_GENERAL",
                message="The 'general' channel cannot be deleted.",
                http_status=status.HTTP_403_FORBIDDEN,
            )

        channel.delete()
        return Response(
            {"message": "Channel deleted successfully."},
            status=status.HTTP_200_OK,
        )
