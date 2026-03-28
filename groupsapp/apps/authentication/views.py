"""
Authentication views – register, login, logout, and token refresh.
"""

from __future__ import annotations

import logging

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.authentication.serializers import LoginSerializer, RegisterSerializer
from apps.authentication.services import AuthService
from apps.core.responses import api_error_response
from apps.users.serializers import PrivateUserSerializer

User = get_user_model()
logger = logging.getLogger("groupsapp")


class RegisterView(APIView):
    """POST /api/auth/register – Create a new account."""

    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error_response(
                code="VALIDATION_ERROR",
                message="Registration failed due to validation errors.",
                details=serializer.errors,
            )
        user = serializer.save()
        tokens = AuthService.generate_tokens(user)
        logger.info("New user registered: %s (id=%s)", user.username, user.id)
        return Response(
            {"user": PrivateUserSerializer(user).data, **tokens},
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    """POST /api/auth/login – Authenticate with email and password."""

    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error_response(
                code="VALIDATION_ERROR",
                message="Login failed due to validation errors.",
                details=serializer.errors,
            )

        email: str = serializer.validated_data["email"]
        password: str = serializer.validated_data["password"]

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return api_error_response(
                code="INVALID_CREDENTIALS",
                message="No account found with this email.",
                http_status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.check_password(password):
            return api_error_response(
                code="INVALID_CREDENTIALS",
                message="Invalid email or password.",
                http_status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return api_error_response(
                code="ACCOUNT_INACTIVE",
                message="This account has been deactivated.",
                http_status=status.HTTP_401_UNAUTHORIZED,
            )

        tokens = AuthService.generate_tokens(user)
        logger.info("User logged in: %s (id=%s)", user.username, user.id)
        return Response(
            {"user": PrivateUserSerializer(user).data, **tokens},
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    """POST /api/auth/logout – Blacklist the refresh token."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        refresh_token: str | None = request.data.get("refresh_token")
        if not refresh_token:
            return api_error_response(
                code="MISSING_TOKEN",
                message="refresh_token is required.",
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            return api_error_response(
                code="INVALID_TOKEN",
                message="Token is invalid or already blacklisted.",
                http_status=status.HTTP_401_UNAUTHORIZED,
            )
        logger.info("User logged out: %s", request.user.username)
        return Response(
            {"message": "Successfully logged out."},
            status=status.HTTP_200_OK,
        )


class RefreshView(APIView):
    """POST /api/auth/refresh – Rotate the JWT refresh token."""

    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        refresh_token: str | None = request.data.get("refresh_token")
        if not refresh_token:
            return api_error_response(
                code="MISSING_TOKEN",
                message="refresh_token is required.",
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            new_refresh = RefreshToken.for_user(
                User.objects.get(id=token["user_id"])
            )
            new_refresh["username"] = token.get("username", "")
            new_refresh["email"] = token.get("email", "")
        except (TokenError, InvalidToken, User.DoesNotExist):
            return api_error_response(
                code="INVALID_TOKEN",
                message="Token is invalid or expired.",
                http_status=status.HTTP_401_UNAUTHORIZED,
            )
        return Response(
            {
                "access_token": str(new_refresh.access_token),
                "refresh_token": str(new_refresh),
            },
            status=status.HTTP_200_OK,
        )
