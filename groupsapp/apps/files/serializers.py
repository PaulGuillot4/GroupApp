from rest_framework import serializers

class FileUploadSerializer(serializers.Serializer):
    """
    Serializer to document the expected fields for file upload.
    Actual validation is handled in the view to provide custom error formatting
    and precise file size/type constraints per file type.
    """
    file = serializers.FileField()
    type = serializers.ChoiceField(choices=["image", "file"])
