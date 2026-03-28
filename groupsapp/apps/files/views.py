import os
import uuid
from django.conf import settings
from django.core.files.storage import default_storage
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import FileUploadSerializer

class FileUploadView(APIView):
    """
    POST /api/files/upload/
    Uploads a file and returns its public URL.
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = FileUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        file_obj = serializer.validated_data["file"]
        file_type = serializer.validated_data["type"]

        # Determine path
        ext = os.path.splitext(file_obj.name)[1]
        filename = f"{uuid.uuid4()}{ext}"
        folder = "chat_images" if file_type == "image" else "chat_files"
        path = os.path.join(folder, filename)

        # Save file
        saved_path = default_storage.save(path, file_obj)
        file_url = settings.MEDIA_URL + saved_path

        return Response({
            "url": file_url,
            "filename": file_obj.name,
            "type": file_type
        }, status=status.HTTP_201_CREATED)
