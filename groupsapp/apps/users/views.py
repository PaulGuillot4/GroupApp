from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.serializers import (
    PrivateUserSerializer,
    PublicUserSerializer,
    UpdateMeSerializer,
)

User = get_user_model()


def _error(code: str, message: str, details=None, http_status=status.HTTP_400_BAD_REQUEST):
    payload = {"error": {"code": code, "message": message}}
    if details is not None:
        payload["error"]["details"] = details
    return Response(payload, status=http_status)


class MeView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        serializer = PrivateUserSerializer(request.user)
        return Response(serializer.data)

    def put(self, request):
        serializer = UpdateMeSerializer(
            request.user,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        if not serializer.is_valid():
            return _error(
                code="VALIDATION_ERROR",
                message="Profile update failed due to validation errors.",
                details=serializer.errors,
            )
        serializer.save()
        return Response(PrivateUserSerializer(request.user).data)


class UserDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return _error(
                code="USER_NOT_FOUND",
                message=f"User with id '{user_id}' does not exist.",
                http_status=status.HTTP_404_NOT_FOUND,
            )
        serializer = PublicUserSerializer(user)
        return Response(serializer.data)
