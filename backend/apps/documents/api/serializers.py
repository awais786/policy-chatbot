"""
DRF serializers for the documents app.

Serializers for Document upload, list, detail, and status responses.
"""

from django.conf import settings
from rest_framework import serializers

from apps.documents.models import Document


class DocumentUploadSerializer(serializers.Serializer):
    """Accepts a file upload and an optional title."""

    file = serializers.FileField()
    title = serializers.CharField(max_length=500, required=False, allow_blank=True)

    def validate_file(self, value):
        if value.size > settings.MAX_UPLOAD_SIZE:
            limit_mb = settings.MAX_UPLOAD_SIZE // (1024 * 1024)
            raise serializers.ValidationError(
                f"File size exceeds the {limit_mb} MB limit."
            )
        if value.content_type not in settings.ALLOWED_DOCUMENT_TYPES:
            allowed = ", ".join(settings.ALLOWED_DOCUMENT_TYPES)
            raise serializers.ValidationError(
                f"Unsupported file type '{value.content_type}'. Allowed: {allowed}"
            )
        return value


class DocumentListSerializer(serializers.ModelSerializer):
    """Read-only serializer for document listings."""

    class Meta:
        model = Document
        fields = [
            "id",
            "title",
            "status",
            "file_hash",
            "metadata",
            "created_at",
            "updated_at",
            "processed_at",
        ]
        read_only_fields = fields


class DocumentDetailSerializer(serializers.ModelSerializer):
    """Read-only serializer for a single document with full details."""

    organization = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    file_url = serializers.SerializerMethodField()
    is_processed = serializers.BooleanField(read_only=True)

    class Meta:
        model = Document
        fields = [
            "id",
            "title",
            "organization",
            "status",
            "file_url",
            "file_hash",
            "metadata",
            "created_by",
            "created_at",
            "updated_at",
            "processed_at",
            "is_processed",
        ]
        read_only_fields = fields

    def get_file_url(self, obj):
        if obj.file:
            return obj.file.url
        return None
