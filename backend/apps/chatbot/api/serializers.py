"""
Serializers for chatbot API endpoints.
"""

import re

from rest_framework import serializers

from apps.chatbot.models import SearchQuery
from apps.documents.models import DocumentChunk

_STRIP_TAGS_RE = re.compile(r"<[^>]+>")
_SESSION_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


def _strip_html(value: str) -> str:
    """Remove HTML tags from a string."""
    return _STRIP_TAGS_RE.sub("", value)


class SearchResultSerializer(serializers.ModelSerializer):
    """Serializer for DocumentChunk search results."""

    document_title = serializers.CharField(source="document.title", read_only=True)
    similarity_score = serializers.FloatField(read_only=True)

    class Meta:
        model = DocumentChunk
        fields = [
            "id",
            "document",
            "document_title",
            "chunk_index",
            "content",
            "similarity_score",
        ]
        read_only_fields = fields


class SearchRequestSerializer(serializers.Serializer):
    """Serializer for search API requests."""

    query = serializers.CharField(
        max_length=2000,
        help_text="Search query text",
    )
    limit = serializers.IntegerField(
        default=10, min_value=1, max_value=50,
        help_text="Number of results to return",
    )
    min_similarity = serializers.FloatField(
        default=0.3, min_value=0.0, max_value=1.0,
        help_text="Minimum similarity threshold",
    )
    organization_id = serializers.CharField(
        required=False,
        help_text="Organization ID (optional, can also use X-API-Key header)",
    )

    def validate_query(self, value: str) -> str:
        value = _strip_html(value).strip()
        if not value:
            raise serializers.ValidationError("Query cannot be empty or whitespace-only.")
        return value


class ChatRequestSerializer(serializers.Serializer):
    """Serializer for chat API requests."""

    message = serializers.CharField(
        max_length=2000,
        help_text="User message",
    )
    session_id = serializers.CharField(
        max_length=128, required=False,
        help_text="Optional session ID for conversation continuity",
    )
    include_sources = serializers.BooleanField(
        default=True,
        help_text="Include source documents in response",
    )
    organization_id = serializers.CharField(
        required=False,
        help_text="Organization ID (optional, can also use X-API-Key header)",
    )

    def validate_message(self, value: str) -> str:
        value = _strip_html(value).strip()
        if not value:
            raise serializers.ValidationError("Message cannot be empty or whitespace-only.")
        return value

    def validate_session_id(self, value: str) -> str:
        if value and not _SESSION_ID_RE.match(value):
            raise serializers.ValidationError(
                "session_id must contain only alphanumeric characters, hyphens, and underscores."
            )
        return value


class ChatResponseSerializer(serializers.Serializer):
    """Serializer for chat API responses."""

    session_id = serializers.CharField(help_text="Session ID for tracking")
    message = serializers.CharField(help_text="Assistant response")
    sources = SearchResultSerializer(many=True, help_text="Source documents used")
    metadata = serializers.DictField(help_text="Additional response metadata")


class SearchQuerySerializer(serializers.ModelSerializer):
    """Serializer for SearchQuery analytics model."""

    class Meta:
        model = SearchQuery
        fields = [
            "id",
            "organization",
            "query_text",
            "results_count",
            "user",
            "session_id",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
