"""
Domain-specific exceptions for GroupsApp.

These are caught by the custom DRF exception handler defined in
``apps.core.exception_handler`` and converted into standardised JSON
error responses automatically.
"""

from __future__ import annotations


class GroupsAppException(Exception):
    """Base exception for all domain errors."""

    default_code: str = "APP_ERROR"
    default_message: str = "An unexpected error occurred."
    default_http_status: int = 400

    def __init__(
        self,
        message: str | None = None,
        code: str | None = None,
        http_status: int | None = None,
    ) -> None:
        self.message = message or self.default_message
        self.code = code or self.default_code
        self.http_status = http_status or self.default_http_status
        super().__init__(self.message)


class NotFoundException(GroupsAppException):
    default_code = "NOT_FOUND"
    default_message = "The requested resource was not found."
    default_http_status = 404


class ForbiddenException(GroupsAppException):
    default_code = "FORBIDDEN"
    default_message = "You do not have permission to perform this action."
    default_http_status = 403


class ValidationException(GroupsAppException):
    default_code = "VALIDATION_ERROR"
    default_message = "The provided data is invalid."
    default_http_status = 400


class ConflictException(GroupsAppException):
    default_code = "CONFLICT"
    default_message = "The action conflicts with existing data."
    default_http_status = 409
