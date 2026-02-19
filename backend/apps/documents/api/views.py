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
    DocumentUploadSerializer,
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


class DocumentUploadView(generics.CreateAPIView):
    """POST — upload a new document."""

    permission_classes = [AllowAny, HasOrganization]
    serializer_class = DocumentUploadSerializer

    def create(self, request, *args, **kwargs):
        """Handle document upload and return the created document."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Create the document
        document = serializer.save()

        # Return the created document details
        response_serializer = DocumentDetailSerializer(document, context={'request': request})

        return Response(
            {
                "message": "Document uploaded successfully. Processing will start automatically.",
                "document": response_serializer.data
            },
            status=status.HTTP_201_CREATED
        )


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


class DocumentProcessView(APIView):
    """POST — trigger document processing for a specific document."""

    permission_classes = [AllowAny, HasOrganization]

    def _get_document(self, request, pk):
        try:
            return Document.objects.for_organization(request.organization).get(pk=pk)
        except Document.DoesNotExist:
            return None

    def post(self, request, pk):
        """Trigger processing for a specific document."""
        document = self._get_document(request, pk)
        if not document:
            return Response(
                {"detail": "Document not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if document.status == Document.Status.COMPLETED:
            return Response(
                {"message": "Document already processed"},
                status=status.HTTP_200_OK
            )

        try:
            # Use the unified processor
            result = document.process_document()

            return Response({
                "message": "Document processed successfully",
                "result": result
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": f"Processing failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
