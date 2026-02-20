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


class DocumentUploadSerializer(serializers.ModelSerializer):
    """Serializer for uploading new documents."""

    file = serializers.FileField(required=True)
    title = serializers.CharField(max_length=500, required=True)

    class Meta:
        model = Document
        fields = ["title", "file"]

    def create(self, validated_data):
        """Create a document with the uploaded file."""
        request = self.context.get('request')
        organization = getattr(request, 'organization', None)

        if not organization:
            raise serializers.ValidationError("Organization not found in request")

        # Create the document
        document = Document.objects.create(
            title=validated_data['title'],
            file=validated_data['file'],
            organization=organization,
            created_by=getattr(request.user, 'pk', None) if request.user.is_authenticated else None,
            status=Document.Status.PENDING
        )

        return document
