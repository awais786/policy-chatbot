"""
API views for document management.

Endpoints for upload, list, detail, and delete.
"""

import logging

from rest_framework import generics, parsers, status
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.documents.models import Document
from apps.documents.services.storage import compute_file_hash

from .serializers import (
    DocumentDetailSerializer,
    DocumentListSerializer,
    DocumentUploadSerializer,
)

logger = logging.getLogger(__name__)


class HasOrganization(BasePermission):
    """Allows access only when the request carries a valid organization."""

    message = "A valid API key with an associated organization is required."

    def has_permission(self, request, view):
        return getattr(request, "organization", None) is not None


class DocumentUploadView(APIView):
    """POST — upload a document file."""

    permission_classes = [AllowAny, HasOrganization]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def post(self, request):
        serializer = DocumentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uploaded_file = serializer.validated_data["file"]
        title = serializer.validated_data.get("title") or uploaded_file.name

        file_hash = compute_file_hash(uploaded_file)

        metadata = {
            "original_filename": uploaded_file.name,
            "file_size": uploaded_file.size,
            "mime_type": uploaded_file.content_type or "application/octet-stream",
        }

        document = Document.objects.create(
            organization=request.organization,
            title=title,
            file=uploaded_file,
            file_hash=file_hash,
            metadata=metadata,
            created_by=request.user if request.user.is_authenticated else None,
        )

        response_serializer = DocumentDetailSerializer(document)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class DocumentListView(generics.ListAPIView):
    """GET — list documents for the current organization."""

    permission_classes = [AllowAny, HasOrganization]
    serializer_class = DocumentListSerializer

    def get_queryset(self):
        return Document.objects.for_organization(self.request.organization)


class DocumentDetailView(generics.RetrieveAPIView):
    """GET — retrieve a single document by UUID."""

    permission_classes = [AllowAny, HasOrganization]
    serializer_class = DocumentDetailSerializer
    lookup_field = "pk"

    def get_queryset(self):
        return Document.objects.for_organization(self.request.organization)


class DocumentDeleteView(APIView):
    """DELETE — remove a document and its stored file."""

    permission_classes = [AllowAny, HasOrganization]

    def delete(self, request, pk):
        try:
            document = Document.objects.for_organization(
                request.organization
            ).get(pk=pk)
        except Document.DoesNotExist:
            return Response(
                {"detail": "Document not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if document.file:
            document.file.delete(save=False)

        document.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
