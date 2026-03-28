"""
Custom DRF exception handler that catches ``GroupsAppException`` subclasses
and returns standardised JSON error responses.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from apps.core.exceptions import GroupsAppException

logger = logging.getLogger("groupsapp")


def custom_exception_handler(
    exc: Exception,
    context: Any,
) -> Optional[Response]:
    """
    Extend the default DRF handler to also handle our domain exceptions.
    """
    # Let DRF handle its own exceptions first (validation, auth, etc.)
    response = drf_exception_handler(exc, context)
    if response is not None:
        return response

    # Handle our domain exceptions
    if isinstance(exc, GroupsAppException):
        payload: dict[str, Any] = {
            "error": {
                "code": exc.code,
                "message": exc.message,
            }
        }
        return Response(payload, status=exc.http_status)

    # Unhandled exception – log it but don't expose internals
    logger.exception("Unhandled exception in view: %s", exc)
    return None
