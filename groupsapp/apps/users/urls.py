from django.urls import path

from apps.users.views import MeView, UserDetailView

app_name = "users"

urlpatterns = [
    path("me", MeView.as_view(), name="me"),
    path("<int:user_id>", UserDetailView.as_view(), name="user-detail"),
]
