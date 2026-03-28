"""
Standardised API response helpers used across all GroupsApp views.

Every error response follows the shape:
    {
        "error": {
            "code": "SOME_CODE",
            "message": "Human-readable explanation.",
            "details": { ... }          # optional
        }
    }
"""

from __future__ import annotations

from typing import Any, Optional

from rest_framework import status
from rest_framework.response import Response


def api_error_response(
    code: str,
    message: str,
    details: Optional[Any] = None,
    http_status: int = status.HTTP_400_BAD_REQUEST,
) -> Response:
    """Return a consistently formatted JSON error response."""
    payload: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details is not None:
        payload["error"]["details"] = details
    return Response(payload, status=http_status)
