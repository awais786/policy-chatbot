"""
URL patterns for the documents API (mounted at api/v1/documents/).
"""

from django.urls import path

from .views import DocumentDetailDeleteView, DocumentListView

app_name = "documents"

urlpatterns = [
    path("", DocumentListView.as_view(), name="document-list"),
    path("<uuid:pk>/", DocumentDetailDeleteView.as_view(), name="document-detail"),
]
