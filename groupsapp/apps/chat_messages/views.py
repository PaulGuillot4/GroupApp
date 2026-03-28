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


class ConversationListView(APIView):
    """
    GET /api/messages/conversations/
    Returns a consolidated list of groups and private chats the user is active in.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # 1. Get all unique users I've chatted with
        sent_to = Message.objects.filter(sender=request.user, type="private").values_list("receiver", flat=True)
        received_from = Message.objects.filter(receiver=request.user, type="private").values_list("sender", flat=True)
        user_ids = set(list(sent_to) + list(received_from))
        
        users = User.objects.filter(id__in=user_ids)
        user_data = []
        for u in users:
            last_msg = Message.objects.filter(
                Q(sender=request.user, receiver=u) | Q(sender=u, receiver=request.user),
                type="private"
            ).order_by("-created_at").first()
            ts = last_msg.created_at if last_msg else u.date_joined
            user_data.append({
                "kind": "private",
                "id": u.id,
                "name": u.username,
                "avatar": str(u.avatar) if hasattr(u, 'avatar') and u.avatar else None,
                "last_message": MessageSerializer(last_msg).data if last_msg else None,
                "updated_at": ts.isoformat() if ts else "",
                "_sort_dt": ts,
            })

        # 2. Get all groups I'm in
        from apps.groups.models import GroupMember
        memberships = GroupMember.objects.filter(user=request.user).select_related("group")
        group_data = []
        for m in memberships:
            g = m.group
            last_msg = Message.objects.filter(group=g, type="group").order_by("-created_at").first()
            ts = last_msg.created_at if last_msg else g.created_at
            group_data.append({
                "kind": "group",
                "id": str(g.id),
                "name": g.name,
                "avatar": None,
                "last_message": MessageSerializer(last_msg).data if last_msg else None,
                "updated_at": ts.isoformat() if ts else "",
                "_sort_dt": ts,
            })

        # 3. Merge and sort by updated_at
        all_convs = user_data + group_data
        all_convs.sort(key=lambda x: x["_sort_dt"], reverse=True)
        
        # Remove internal sort key before sending
        for c in all_convs:
            c.pop("_sort_dt")

        return Response(all_convs)
