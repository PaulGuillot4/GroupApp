"""
Group domain services – encapsulate business logic that was previously
embedded in the view layer.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Sequence

from django.contrib.auth import get_user_model
from django.db import transaction

from apps.groups.models import Channel, Group, GroupMember

User = get_user_model()
logger = logging.getLogger("groupsapp")


class GroupService:
    """Encapsulates group creation / mutation logic."""

    @staticmethod
    @transaction.atomic
    def create_group(
        *,
        owner: Any,
        name: str,
        description: str = "",
        avatar: Any = None,
        subscription_type: str = "open",
        initial_member_ids: Sequence[int] | None = None,
    ) -> Group:
        """
        Create a new group, add the owner as admin, add initial members,
        and create the default *general* channel.
        """
        group: Group = Group.objects.create(
            owner=owner,
            name=name,
            description=description,
            avatar=avatar,
            subscription_type=subscription_type,
        )

        # Owner is always an admin
        GroupMember.objects.get_or_create(
            group=group, user=owner, defaults={"role": "admin"}
        )

        # Add initial members
        if initial_member_ids:
            for user_id in initial_member_ids:
                if user_id != owner.id:
                    GroupMember.objects.get_or_create(
                        group=group, user_id=user_id, defaults={"role": "member"}
                    )

        # Default channel
        Channel.objects.get_or_create(group=group, name="general")

        logger.info("Group '%s' (id=%s) created by user %s", name, group.id, owner.id)
        return group


class MembershipService:
    """Encapsulates member management logic."""

    @staticmethod
    def get_group_or_none(group_id: str) -> Optional[Group]:
        """Fetch a group by primary key, returning ``None`` on failure."""
        try:
            return Group.objects.get(pk=group_id)
        except (Group.DoesNotExist, ValueError):
            return None

    @staticmethod
    def get_channel_or_none(channel_id: str, group: Group) -> Optional[Channel]:
        """Fetch a channel belonging to *group*, returning ``None`` on failure."""
        try:
            return Channel.objects.get(pk=channel_id, group=group)
        except (Channel.DoesNotExist, ValueError):
            return None

    @staticmethod
    def add_member(group: Group, user_id: int) -> GroupMember:
        """Add a user to a group as a regular member."""
        user = User.objects.get(pk=user_id)
        membership: GroupMember = GroupMember.objects.create(
            group=group, user=user, role="member"
        )
        logger.info(
            "User %s added to group '%s' (id=%s)",
            user_id,
            group.name,
            group.id,
        )
        return membership
