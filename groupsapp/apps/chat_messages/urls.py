from django.urls import path

from apps.chat_messages.views import (
    ChannelMessageListView,
    GroupMessageListView,
    PrivateMessageListView,
)

app_name = "chat_messages"

urlpatterns = [
    path("group/<uuid:group_id>/", GroupMessageListView.as_view(), name="group-messages"),
    path("channel/<uuid:channel_id>/", ChannelMessageListView.as_view(), name="channel-messages"),
    path("private/<int:user_id>/", PrivateMessageListView.as_view(), name="private-messages"),
]
