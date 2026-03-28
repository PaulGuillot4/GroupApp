"""
User views – current-user profile and user search.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.serializers import PrivateUserSerializer

User = get_user_model()


class MeView(APIView):
    """GET /api/users/me/ – Return the authenticated user's profile."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return Response(PrivateUserSerializer(request.user).data)


class UserSearchView(APIView):
    """GET /api/users/search/?q=<query> – Search users by name or email."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        query: str = request.query_params.get("q", "").strip()
        if not query:
            return Response([])
        users = User.objects.filter(
            Q(username__icontains=query) | Q(email__icontains=query)
        ).exclude(pk=request.user.pk)[:20]
        return Response(PrivateUserSerializer(users, many=True).data)
