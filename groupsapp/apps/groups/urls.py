from django.urls import path

from apps.groups.views import (
    ChannelDetailView,
    ChannelListCreateView,
    GroupDetailView,
    GroupJoinView,
    GroupLeaveView,
    GroupListCreateView,
    MemberListCreateView,
    MemberRemoveView,
    MemberRoleView,
)

app_name = "groups"

urlpatterns = [
    # Groups
    path("", GroupListCreateView.as_view(), name="group-list-create"),
    path("<uuid:group_id>/", GroupDetailView.as_view(), name="group-detail"),
    path("<uuid:group_id>/join/", GroupJoinView.as_view(), name="group-join"),
    path("<uuid:group_id>/leave/", GroupLeaveView.as_view(), name="group-leave"),
    # Members
    path("<uuid:group_id>/members/", MemberListCreateView.as_view(), name="member-list-create"),
    path("<uuid:group_id>/members/<int:user_id>/", MemberRemoveView.as_view(), name="member-remove"),
    path("<uuid:group_id>/members/<int:user_id>/role/", MemberRoleView.as_view(), name="member-role"),
    # Channels
    path("<uuid:group_id>/channels/", ChannelListCreateView.as_view(), name="channel-list-create"),
    path("<uuid:group_id>/channels/<uuid:channel_id>/", ChannelDetailView.as_view(), name="channel-detail"),
]
