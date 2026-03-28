"""
ASGI config for GroupsApp.

Exposes the ASGI callable as a module-level variable named ``application``.
Routes HTTP and WebSocket protocols separately.
WebSocket connections are authenticated via JWT middleware.
"""

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Initialise Django ASGI application early to populate the AppRegistry.
django_asgi_app = get_asgi_application()

# Import after Django setup
from apps.chat_messages.middleware import JWTAuthMiddleware
from apps.chat_messages.routing import websocket_urlpatterns as messages_ws

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": JWTAuthMiddleware(
            URLRouter(
                messages_ws,
            )
        ),
    }
)
