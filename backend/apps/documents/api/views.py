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
