from django.urls import path
from .views import MeView, UserSearchView

app_name = "users"

urlpatterns = [
    path("me/", MeView.as_view(), name="me"),
    path("search/", UserSearchView.as_view(), name="search"),
]
