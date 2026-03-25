from django.urls import path
from .views import chat_view, login_view, register_view

app_name = "frontend"

urlpatterns = [
    path("", chat_view, name="index"), # Will handle auth redirect in JS
    path("auth/login/", login_view, name="login"),
    path("auth/register/", register_view, name="register"),
    path("app/", chat_view, name="chat"),
]
