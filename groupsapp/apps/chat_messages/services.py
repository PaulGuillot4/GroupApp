"""
Chat-message domain services – encapsulate business logic for conversations
and message history retrieval.
"""

from __future__ import annotations

import logging
from typing import Any

from django.contrib.auth import get_user_model
from django.db.models import Q

from apps.chat_messages.models import Message
from apps.chat_messages.serializers import MessageSerializer
from apps.groups.models import GroupMember

User = get_user_model()
logger = logging.getLogger("groupsapp")


class ConversationService:
    """Builds the consolidated list of private + group conversations."""

    @staticmethod
    def get_conversations(user: Any) -> list[dict[str, Any]]:
        """
        Return a merged, time-sorted list of all conversations (private and
        group) that *user* participates in.
        """
        conversations: list[dict[str, Any]] = []

        # ── Private conversations ──────────────────────────────────────
        sent_to = Message.objects.filter(
            sender=user, type="private"
        ).values_list("receiver", flat=True)
        received_from = Message.objects.filter(
            receiver=user, type="private"
        ).values_list("sender", flat=True)
        partner_ids = set(list(sent_to) + list(received_from))

        for partner in User.objects.filter(id__in=partner_ids):
            last_msg = (
                Message.objects.filter(
                    Q(sender=user, receiver=partner)
                    | Q(sender=partner, receiver=user),
                    type="private",
                )
                .order_by("-created_at")
                .first()
            )
            timestamp = last_msg.created_at if last_msg else partner.date_joined
            conversations.append(
                {
                    "kind": "private",
                    "id": partner.id,
                    "name": partner.username,
                    "avatar": (
                        str(partner.avatar)
                        if hasattr(partner, "avatar") and partner.avatar
                        else None
                    ),
                    "last_message": (
                        MessageSerializer(last_msg).data if last_msg else None
                    ),
                    "updated_at": timestamp.isoformat() if timestamp else "",
                    "_sort_dt": timestamp,
                }
            )

        # ── Group conversations ────────────────────────────────────────
        memberships = GroupMember.objects.filter(user=user).select_related("group")
        for membership in memberships:
            group = membership.group
            last_msg = (
                Message.objects.filter(group=group, type="group")
                .order_by("-created_at")
                .first()
            )
            timestamp = last_msg.created_at if last_msg else group.created_at
            conversations.append(
                {
                    "kind": "group",
                    "id": str(group.id),
                    "name": group.name,
                    "avatar": None,
                    "last_message": (
                        MessageSerializer(last_msg).data if last_msg else None
                    ),
                    "updated_at": timestamp.isoformat() if timestamp else "",
                    "_sort_dt": timestamp,
                }
            )

        # ── Sort by most recent activity ───────────────────────────────
        conversations.sort(key=lambda c: c["_sort_dt"], reverse=True)

        # Remove internal sort key
        for conv in conversations:
            conv.pop("_sort_dt")

        return conversations
