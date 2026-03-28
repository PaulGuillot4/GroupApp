"""
JWT authentication middleware for Django Channels WebSockets.

Validates the token from the query string (?token=<access_token>)
and assigns the user to the scope.  Invalid or missing tokens result
in an ``AnonymousUser`` scope and a warning-level log message.
"""

from __future__ import annotations

import logging
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
logger = logging.getLogger("groupsapp")


@database_sync_to_async
def get_user_from_token(token_string: str):
    """Validate an access token and return the corresponding user."""
    try:
        token = AccessToken(token_string)
        user_id = token["user_id"]
        return User.objects.get(pk=user_id)
    except (TokenError, InvalidToken, User.DoesNotExist, KeyError) as exc:
        logger.warning("WebSocket auth failed: %s", exc)
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """
    Custom middleware that authenticates WebSocket connections
    via a JWT access token passed as a query parameter.

    Usage in ASGI:
        JWTAuthMiddleware(URLRouter(...))

    Client connects with:
        ws://host/ws/chat/?token=<access_token>
    """

    async def __call__(self, scope, receive, send):
        query_string: str = scope.get("query_string", b"").decode("utf-8")
        query_params: dict = parse_qs(query_string)
        token_list: list[str] = query_params.get("token", [])

        if token_list:
            scope["user"] = await get_user_from_token(token_list[0])
        else:
            logger.debug("WebSocket connection without token from %s", scope.get("client"))
            scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)
