from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chat_messages.models import Message
from apps.chat_messages.serializers import MessageSerializer
from apps.groups.models import Channel, Group, GroupMember

User = get_user_model()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _error(code: str, message: str, details=None, http_status=status.HTTP_400_BAD_REQUEST):
    payload = {"error": {"code": code, "message": message}}
    if details is not None:
        payload["error"]["details"] = details
    return Response(payload, status=http_status)


class MessagePagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "limit"
    max_page_size = 100


# ===================================================================
# Group messages
# ===================================================================

class GroupMessageListView(APIView):
    """GET /api/messages/group/:groupId/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, group_id):
        # Check group exists
        try:
            group = Group.objects.get(pk=group_id)
        except (Group.DoesNotExist, ValueError):
            return _error(
                code="GROUP_NOT_FOUND",
                message=f"Group with id '{group_id}' does not exist.",
                http_status=status.HTTP_404_NOT_FOUND,
            )

        # Check membership
        if not GroupMember.objects.filter(group=group, user=request.user).exists():
            return _error(
                code="NOT_A_MEMBER",
                message="You are not a member of this group.",
                http_status=status.HTTP_403_FORBIDDEN,
            )

        messages = Message.objects.filter(
            type="group", group=group
        ).select_related("sender").prefetch_related("statuses__user")

        paginator = MessagePagination()
        page = paginator.paginate_queryset(messages, request)
        serializer = MessageSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


# ===================================================================
# Channel messages
# ===================================================================

class ChannelMessageListView(APIView):
    """GET /api/messages/channel/:channelId/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, channel_id):
        try:
            channel = Channel.objects.select_related("group").get(pk=channel_id)
        except (Channel.DoesNotExist, ValueError):
            return _error(
                code="CHANNEL_NOT_FOUND",
                message=f"Channel with id '{channel_id}' does not exist.",
                http_status=status.HTTP_404_NOT_FOUND,
            )

        if not GroupMember.objects.filter(group=channel.group, user=request.user).exists():
            return _error(
                code="NOT_A_MEMBER",
                message="You are not a member of the group this channel belongs to.",
                http_status=status.HTTP_403_FORBIDDEN,
            )

        messages = Message.objects.filter(
            type="channel", channel=channel
        ).select_related("sender").prefetch_related("statuses__user")

        paginator = MessagePagination()
        page = paginator.paginate_queryset(messages, request)
        serializer = MessageSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


# ===================================================================
# Private messages
# ===================================================================

class PrivateMessageListView(APIView):
    """GET /api/messages/private/:userId/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        # Check target user exists
        try:
            other_user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return _error(
                code="USER_NOT_FOUND",
                message=f"User with id '{user_id}' does not exist.",
                http_status=status.HTTP_404_NOT_FOUND,
            )

        # Removed 'must share a group' restriction to allow normal private messaging

        messages = Message.objects.filter(
            type="private"
        ).filter(
            Q(sender=request.user, receiver=other_user)
            | Q(sender=other_user, receiver=request.user)
        ).select_related("sender").prefetch_related("statuses__user")

        paginator = MessagePagination()
        page = paginator.paginate_queryset(messages, request)
        serializer = MessageSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
