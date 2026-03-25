from django.apps import AppConfig


class ChatMessagesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.chat_messages"
    label = "chat_messages"
    verbose_name = "Messages"
