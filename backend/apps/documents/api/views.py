"""
API views for document management.
"""

import logging

from rest_framework import generics, status
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.documents.models import Document

from .serializers import (
    DocumentDetailSerializer,
    DocumentListSerializer,
)

logger = logging.getLogger(__name__)


class HasOrganization(BasePermission):
    """Allows access only when the request carries a valid organization."""

    message = "A valid API key with an associated organization is required."

    def has_permission(self, request, view):
        return getattr(request, "organization", None) is not None



class DocumentListView(generics.ListAPIView):
    """GET — list documents for the current organization."""

    permission_classes = [AllowAny, HasOrganization]
    serializer_class = DocumentListSerializer

    def get_queryset(self):
        return Document.objects.for_organization(self.request.organization).active()


class DocumentDetailDeleteView(APIView):
    """GET / DELETE a single document by UUID.

    GET  — return document details.
    DELETE — delete the document and its stored file.
    """

    permission_classes = [AllowAny, HasOrganization]

    def _get_document(self, request, pk):
        try:
            return Document.objects.for_organization(request.organization).get(pk=pk)
        except Document.DoesNotExist:
            return None

    def get(self, request, pk):
        document = self._get_document(request, pk)
        if not document:
            return Response(
                {"detail": "Document not found."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = DocumentDetailSerializer(document)
        return Response(serializer.data)

    def delete(self, request, pk):
        document = self._get_document(request, pk)
        if not document:
            return Response(
                {"detail": "Document not found."}, status=status.HTTP_404_NOT_FOUND
            )

        # Delete the file from storage if it exists
        if document.file:
            try:
                document.file.delete(save=False)
            except Exception as e:
                logger.warning(f"Failed to delete file for document {pk}: {e}")

        # Delete the document record
        document.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)
