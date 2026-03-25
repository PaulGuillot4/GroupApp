from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.authentication.serializers import LoginSerializer, RegisterSerializer
from apps.users.serializers import PrivateUserSerializer

User = get_user_model()


def _error(code: str, message: str, details=None, http_status=status.HTTP_400_BAD_REQUEST):
    payload = {"error": {"code": code, "message": message}}
    if details is not None:
        payload["error"]["details"] = details
    return Response(payload, status=http_status)


def _tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    # Embed extra claims
    refresh["username"] = user.username
    refresh["email"] = user.email
    return {
        "refresh_token": str(refresh),
        "access_token": str(refresh.access_token),
    }


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return _error(
                code="VALIDATION_ERROR",
                message="Registration failed due to validation errors.",
                details=serializer.errors,
            )
        user = serializer.save()
        tokens = _tokens_for_user(user)
        return Response(
            {"user": PrivateUserSerializer(user).data, **tokens},
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return _error(
                code="VALIDATION_ERROR",
                message="Login failed due to validation errors.",
                details=serializer.errors,
            )

        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return _error(
                code="INVALID_CREDENTIALS",
                message="No account found with this email.",
                http_status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.check_password(password):
            return _error(
                code="INVALID_CREDENTIALS",
                message="Invalid email or password.",
                http_status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return _error(
                code="ACCOUNT_INACTIVE",
                message="This account has been deactivated.",
                http_status=status.HTTP_401_UNAUTHORIZED,
            )

        tokens = _tokens_for_user(user)
        return Response(
            {"user": PrivateUserSerializer(user).data, **tokens},
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh_token")
        if not refresh_token:
            return _error(
                code="MISSING_TOKEN",
                message="refresh_token is required.",
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            return _error(
                code="INVALID_TOKEN",
                message="Token is invalid or already blacklisted.",
                http_status=status.HTTP_401_UNAUTHORIZED,
            )
        return Response({"message": "Successfully logged out."}, status=status.HTTP_200_OK)


class RefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.data.get("refresh_token")
        if not refresh_token:
            return _error(
                code="MISSING_TOKEN",
                message="refresh_token is required.",
            )
        try:
            token = RefreshToken(refresh_token)
            # Rotate: blacklist old, issue new
            token.blacklist()
            new_refresh = RefreshToken.for_user(
                User.objects.get(id=token["user_id"])
            )
            new_refresh["username"] = token.get("username", "")
            new_refresh["email"] = token.get("email", "")
        except (TokenError, InvalidToken, User.DoesNotExist):
            return _error(
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
