"""
URL patterns for the documents API (mounted at api/v1/documents/).
"""

from django.urls import path

from .views import (
    DocumentDeleteView,
    DocumentDetailView,
    DocumentListView,
    DocumentUploadView,
)

app_name = "documents"

urlpatterns = [
    path("upload/", DocumentUploadView.as_view(), name="document-upload"),
    path("", DocumentListView.as_view(), name="document-list"),
    path("<uuid:pk>/", DocumentDetailView.as_view(), name="document-detail"),
    path("<uuid:pk>/delete/", DocumentDeleteView.as_view(), name="document-delete"),
]
