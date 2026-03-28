"""
File upload view – validates, saves, and returns the public URL.
"""

from __future__ import annotations

import logging
import os
import uuid

from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import UploadedFile
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.responses import api_error_response
from apps.files.serializers import FileUploadSerializer

logger = logging.getLogger("groupsapp")

# Limits (configurable via settings)
MAX_IMAGE_SIZE: int = getattr(settings, "MAX_IMAGE_UPLOAD_SIZE", 10 * 1024 * 1024)  # 10 MB
MAX_FILE_SIZE: int = getattr(settings, "MAX_FILE_UPLOAD_SIZE", 50 * 1024 * 1024)    # 50 MB

ALLOWED_IMAGE_EXTENSIONS: set[str] = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
ALLOWED_FILE_EXTENSIONS: set[str] = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".txt", ".csv", ".zip", ".rar", ".7z",
}


class FileUploadView(APIView):
    """
    POST /api/files/upload/

    Uploads a file and returns its public URL.
    Validates size limits and file extensions to prevent malicious uploads.
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request: Request) -> Response:
        serializer = FileUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error_response(
                code="VALIDATION_ERROR",
                message="File upload failed due to validation errors.",
                details=serializer.errors,
            )

        file_obj: UploadedFile = serializer.validated_data["file"]
        file_type: str = serializer.validated_data["type"]

        # ── Extension validation ───────────────────────────────────────
        ext: str = os.path.splitext(file_obj.name)[1].lower()
        if file_type == "image" and ext not in ALLOWED_IMAGE_EXTENSIONS:
            return api_error_response(
                code="INVALID_FILE_TYPE",
                message=f"Image extension '{ext}' is not allowed. "
                        f"Accepted: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}",
            )
        if file_type == "file" and ext not in ALLOWED_FILE_EXTENSIONS:
            return api_error_response(
                code="INVALID_FILE_TYPE",
                message=f"File extension '{ext}' is not allowed. "
                        f"Accepted: {', '.join(sorted(ALLOWED_FILE_EXTENSIONS))}",
            )

        # ── Size validation ────────────────────────────────────────────
        max_size: int = MAX_IMAGE_SIZE if file_type == "image" else MAX_FILE_SIZE
        if file_obj.size and file_obj.size > max_size:
            max_mb: float = max_size / (1024 * 1024)
            return api_error_response(
                code="FILE_TOO_LARGE",
                message=f"File exceeds the maximum size of {max_mb:.0f} MB.",
            )

        # ── Save ───────────────────────────────────────────────────────
        filename: str = f"{uuid.uuid4()}{ext}"
        folder: str = "chat_images" if file_type == "image" else "chat_files"
        path: str = os.path.join(folder, filename)

        saved_path: str = default_storage.save(path, file_obj)
        file_url: str = settings.MEDIA_URL + saved_path

        logger.info(
            "File uploaded by user %s: %s (%s, %s bytes)",
            request.user.id,
            file_obj.name,
            file_type,
            file_obj.size,
        )

        return Response(
            {"url": file_url, "filename": file_obj.name, "type": file_type},
            status=status.HTTP_201_CREATED,
        )
