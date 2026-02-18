"""
Chatbot models for search query analytics.
"""

import uuid
from django.conf import settings
from django.db import models

from apps.core.models import Organization, TimeStampedModel


class SearchQuery(TimeStampedModel):
    """Track search queries for analytics and improvement."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="search_queries"
    )
    query_text = models.TextField()
    results_count = models.IntegerField(default=0)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="search_queries",
    )
    # Optional: track session ID in memory without persisting the session
    session_id = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        db_table = "search_queries"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "created_at"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self):
        return f"Search: {self.query_text[:50]}..."
