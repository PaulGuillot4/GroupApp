"""
Chat-message views – REST endpoints for message history and conversations.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chat_messages.models import Message
from apps.chat_messages.serializers import MessageSerializer
from apps.chat_messages.services import ConversationService
from apps.core.responses import api_error_response
from apps.groups.models import Channel, Group, GroupMember

User = get_user_model()


class MessagePagination(PageNumberPagination):
    """Standard pagination for paginated message endpoints."""

    page_size = 50
    page_size_query_param = "limit"
    max_page_size = 100


# ===================================================================
# Group messages
# ===================================================================


class GroupMessageListView(APIView):
    """GET /api/messages/group/:groupId/ – Paginated group message history."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, group_id: str) -> Response:
        try:
            group: Group = Group.objects.get(pk=group_id)
        except (Group.DoesNotExist, ValueError):
            return api_error_response(
                code="GROUP_NOT_FOUND",
                message=f"Group with id '{group_id}' does not exist.",
                http_status=status.HTTP_404_NOT_FOUND,
            )

        if not GroupMember.objects.filter(group=group, user=request.user).exists():
            return api_error_response(
                code="NOT_A_MEMBER",
                message="You are not a member of this group.",
                http_status=status.HTTP_403_FORBIDDEN,
            )

        messages = (
            Message.objects.filter(type="group", group=group)
            .select_related("sender")
            .prefetch_related("statuses__user")
        )

        paginator = MessagePagination()
        page = paginator.paginate_queryset(messages, request)
        serializer = MessageSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


# ===================================================================
# Channel messages
# ===================================================================


class ChannelMessageListView(APIView):
    """GET /api/messages/channel/:channelId/ – Paginated channel message history."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, channel_id: str) -> Response:
        try:
            channel: Channel = Channel.objects.select_related("group").get(
                pk=channel_id
            )
        except (Channel.DoesNotExist, ValueError):
            return api_error_response(
                code="CHANNEL_NOT_FOUND",
                message=f"Channel with id '{channel_id}' does not exist.",
                http_status=status.HTTP_404_NOT_FOUND,
            )

        if not GroupMember.objects.filter(
            group=channel.group, user=request.user
        ).exists():
            return api_error_response(
                code="NOT_A_MEMBER",
                message="You are not a member of the group this channel belongs to.",
                http_status=status.HTTP_403_FORBIDDEN,
            )

        messages = (
            Message.objects.filter(type="channel", channel=channel)
            .select_related("sender")
            .prefetch_related("statuses__user")
        )

        paginator = MessagePagination()
        page = paginator.paginate_queryset(messages, request)
        serializer = MessageSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


# ===================================================================
# Private messages
# ===================================================================


class PrivateMessageListView(APIView):
    """GET /api/messages/private/:userId/ – Paginated private message history."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, user_id: int) -> Response:
        try:
            other_user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return api_error_response(
                code="USER_NOT_FOUND",
                message=f"User with id '{user_id}' does not exist.",
                http_status=status.HTTP_404_NOT_FOUND,
            )

        messages = (
            Message.objects.filter(type="private")
            .filter(
                Q(sender=request.user, receiver=other_user)
                | Q(sender=other_user, receiver=request.user)
            )
            .select_related("sender")
            .prefetch_related("statuses__user")
        )

        paginator = MessagePagination()
        page = paginator.paginate_queryset(messages, request)
        serializer = MessageSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


# ===================================================================
# Conversations
# ===================================================================


class ConversationListView(APIView):
    """
    GET /api/messages/conversations/

    Returns a consolidated list of groups and private chats the user
    participates in, sorted by most-recent activity.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        conversations = ConversationService.get_conversations(request.user)
        return Response(conversations)
