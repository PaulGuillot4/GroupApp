from rest_framework.permissions import BasePermission

from apps.groups.models import GroupMember


class IsGroupMember(BasePermission):
    """Allow access only to members of the group."""

    message = "You are not a member of this group."

    def has_permission(self, request, view):
        group_id = view.kwargs.get("group_id")
        if group_id is None:
            return True
        return GroupMember.objects.filter(
            group_id=group_id, user=request.user
        ).exists()


class IsGroupAdmin(BasePermission):
    """Allow access only to admins (or the owner) of the group."""

    message = "You must be an admin of this group to perform this action."

    def has_permission(self, request, view):
        group_id = view.kwargs.get("group_id")
        if group_id is None:
            return True
        return GroupMember.objects.filter(
            group_id=group_id, user=request.user, role="admin"
        ).exists()


class IsGroupOwner(BasePermission):
    """Allow access only to the owner of the group."""

    message = "You must be the owner of this group to perform this action."

    def has_permission(self, request, view):
        group_id = view.kwargs.get("group_id")
        if group_id is None:
            return True
        from apps.groups.models import Group

        try:
            group = Group.objects.get(pk=group_id)
        except Group.DoesNotExist:
            return False
        return group.owner == request.user
