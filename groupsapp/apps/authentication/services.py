"""
Authentication services – business logic decoupled from views.
"""

from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


class AuthService:
    """Handles token generation and authentication logic."""

    @staticmethod
    def generate_tokens(user: Any) -> dict[str, str]:
        """
        Issue a JWT access/refresh pair for *user*, embedding extra claims
        (username and email) in the refresh token.
        """
        refresh: RefreshToken = RefreshToken.for_user(user)
        refresh["username"] = user.username
        refresh["email"] = user.email
        return {
            "refresh_token": str(refresh),
            "access_token": str(refresh.access_token),
        }
