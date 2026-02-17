"""
DRF serializers for the documents app.
"""

from rest_framework import serializers

from apps.documents.models import Document



class DocumentListSerializer(serializers.ModelSerializer):
    """Read-only serializer for document listings."""

    class Meta:
        model = Document
        fields = [
            "id",
            "title",
            "status",
            "is_active",
            "file_hash",
            "text_content",
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
            "is_active",
            "file_url",
            "file_hash",
            "text_content",
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
