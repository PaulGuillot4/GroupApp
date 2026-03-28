from django.urls import path
from .views import index_view, login_view, register_view, chat_view

app_name = "frontend"

urlpatterns = [
    path("", index_view, name="index"),          # Redirige a /app/ si hay token
    path("auth/login/", login_view, name="login"),
    path("auth/register/", register_view, name="register"),
    path("app/", chat_view, name="chat"),
]
