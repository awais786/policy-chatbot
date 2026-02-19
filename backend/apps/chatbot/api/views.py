"""
API views for chatbot functionality - search and chat endpoints.
"""

import logging
import uuid

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.chatbot.api.serializers import (
    ChatRequestSerializer,
    SearchRequestSerializer,
)
from apps.chatbot.models import SearchQuery
from apps.chatbot.services.chat_history import get_chat_store_stats
from apps.chatbot.services.providers import create_rag_chatbot
from apps.chatbot.services.search import VectorSearchService

logger = logging.getLogger(__name__)


def _get_organization_id(request, data=None) -> str:
    """Extract organization ID from the request.

    Resolution order:
      1. organization_id in request body
      2. request.organization set by APIKeyAuthMiddleware
      3. DEFAULT_ORGANIZATION_ID from settings
    """
    if data and "organization_id" in data:
        return str(data["organization_id"])

    org = getattr(request, "organization", None)
    if org is not None:
        return str(org.id)

    default_org = getattr(settings, "DEFAULT_ORGANIZATION_ID", None)
    if default_org:
        return str(default_org)

    raise ValueError(
        "No organization resolved. Set DEFAULT_ORGANIZATION_ID in settings."
    )


@api_view(["POST"])
@permission_classes([AllowAny])  # No authentication required for testing
def search_documents(request):
    """
    Semantic search endpoint for finding relevant document chunks.

    POST /api/v1/chat/search/
    Can use either X-API-Key header or organization_id in request body.
    """
    serializer = SearchRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    try:
        organization_id = _get_organization_id(request, request.data)
    except ValueError as exc:
        return Response(
            {"error": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,  # Changed from 401 to 400
        )

    query = serializer.validated_data["query"]
    limit = serializer.validated_data.get("limit", 10)
    min_similarity = serializer.validated_data.get("min_similarity", 0.7)
    session_id = request.data.get("session_id") or None

    try:
        search_service = VectorSearchService(organization_id)
        results = search_service.search(
            query=query,
            limit=limit,
            min_similarity=min_similarity,
        )

        # Best-effort analytics write; do not fail user request on logging errors.
        try:
            SearchQuery.objects.create(
                organization_id=organization_id,
                query_text=query,
                results_count=len(results),
                user=request.user if getattr(request, "user", None) and request.user.is_authenticated else None,
                session_id=session_id,
            )
        except Exception:
            logger.exception("Failed to persist search analytics")

        return Response(
            {
                "query": query,
                "results_count": len(results),
                "results": results,
            },
            status=status.HTTP_200_OK,
        )

    except ValueError as exc:
        return Response(
            {"error": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception:
        logger.exception("Search failed")
        return Response(
            {"error": "An internal error occurred while processing your search."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([AllowAny])  # No authentication required for testing
def chat_with_documents(request):
    """
    Chat endpoint that combines search with LLM for conversational responses.

    POST /api/v1/chat/
    Can use either X-API-Key header or organization_id in request body.
    """
    serializer = ChatRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    try:
        organization_id = _get_organization_id(request, request.data)
    except ValueError as exc:
        return Response(
            {"error": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,  # Changed from 401 to 400
        )

    user_message = serializer.validated_data["message"]
    session_id = serializer.validated_data.get("session_id") or str(uuid.uuid4())
    include_sources = serializer.validated_data.get("include_sources", True)
    top_k = int(getattr(settings, "DEFAULT_TOP_K", 5) or 5)
    min_similarity = float(
        getattr(settings, "DEFAULT_SIMILARITY_THRESHOLD", 0.3) or 0.3
    )

    try:
        search_service = VectorSearchService(organization_id)
        search_results = search_service.search(
            query=user_message,
            limit=top_k,
            min_similarity=min_similarity,
        )

        chatbot = create_rag_chatbot(organization_id)
        result = chatbot.generate_answer(user_message, search_results, session_id)

        # Best-effort analytics write for chat turn.
        try:
            SearchQuery.objects.create(
                organization_id=organization_id,
                query_text=user_message,
                results_count=len(search_results),
                user=request.user if getattr(request, "user", None) and request.user.is_authenticated else None,
                session_id=session_id,
            )
        except Exception:
            logger.exception("Failed to persist chat analytics")

        return Response(
            {
                "session_id": session_id,
                "message": result["answer"],
                "sources": search_results if include_sources else [],
                "metadata": {
                    "sources_used": result["sources_used"],
                    "provider": result.get("provider"),
                    "model": result.get("model"),
                    "history_enabled": result["history_enabled"],
                },
            },
            status=status.HTTP_200_OK,
        )

    except ValueError as exc:
        return Response(
            {"error": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception:
        logger.exception("Chat failed")
        return Response(
            {"error": "An internal error occurred while processing your message."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([AllowAny])  # TODO: Replace with proper permission class
def chat_stats(request):
    """Get statistics about in-memory chat sessions."""
    try:
        stats = get_chat_store_stats()
        return Response({"status": "success", "stats": stats})
    except Exception:
        logger.exception("Failed to get chat stats")
        return Response(
            {"error": "Failed to retrieve chat statistics."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    """Simple health check endpoint for the chatbot service."""
    return Response({"status": "healthy", "service": "chatbot", "version": "1.0"})
