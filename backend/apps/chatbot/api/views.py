"""
API views for chatbot functionality - search and chat endpoints.
"""

import logging
import uuid
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.chatbot.api.serializers import (
    SearchRequestSerializer,
    SearchResultSerializer,
    ChatRequestSerializer,
    ChatResponseSerializer,
)
from apps.chatbot.services.search import VectorSearchService
from apps.chatbot.models import SearchQuery

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([AllowAny])  # TODO: Add proper authentication
def search_documents(request):
    """
    Semantic search endpoint for finding relevant document chunks.

    POST /api/v1/chat/search/
    {
        "query": "traffic violation penalties",
        "limit": 10,
        "min_similarity": 0.7
    }
    """
    # TODO: Get organization from request authentication
    organization_id = "44e5dfd8-1d6d-4229-a151-02f37baea1d5"  # Temporary hardcode

    # Validate request data
    serializer = SearchRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    query = serializer.validated_data['query']
    limit = serializer.validated_data.get('limit', 10)
    min_similarity = serializer.validated_data.get('min_similarity', 0.7)

    try:
        # Perform vector search
        search_service = VectorSearchService(organization_id)
        results = search_service.search(
            query=query,
            limit=limit,
            min_similarity=min_similarity
        )

        # Log search query for analytics
        SearchQuery.objects.create(
            organization_id=organization_id,
            query_text=query,
            results_count=len(results),
            user=request.user if request.user.is_authenticated else None,
        )

        # Format response
        response_data = {
            "query": query,
            "results_count": len(results),
            "results": results
        }

        return Response(response_data, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Search failed for query '{query}': {e}")
        return Response(
            {"error": "Search failed", "detail": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])  # TODO: Add proper authentication
def chat_with_documents(request):
    """
    Chat endpoint that combines search with LLM for conversational responses.

    POST /api/v1/chat/
    {
        "message": "What are the penalties for traffic violations?",
        "session_id": "optional-session-id" (optional),
        "include_sources": true
    }
    """
    # TODO: Get organization from request authentication
    organization_id = "44e5dfd8-1d6d-4229-a151-02f37baea1d5"  # Temporary hardcode

    # Validate request data
    serializer = ChatRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    user_message = serializer.validated_data['message']
    session_id = serializer.validated_data.get('session_id') or str(uuid.uuid4())
    include_sources = serializer.validated_data.get('include_sources', True)

    try:
        # Perform vector search to find relevant documents
        search_service = VectorSearchService(organization_id)
        search_results = search_service.search(
            query=user_message,
            limit=5,
            min_similarity=0.7
        )

        # Generate answer using RAG chatbot with session history
        from apps.chatbot.services.providers import create_rag_chatbot
        chatbot = create_rag_chatbot(organization_id)

        result = chatbot.generate_answer(user_message, search_results, session_id)

        # Log search query for analytics (without persisting session)
        SearchQuery.objects.create(
            organization_id=organization_id,
            query_text=user_message,
            results_count=len(search_results),
            user=request.user if request.user.is_authenticated else None,
            session_id=session_id,  # Track session ID for analytics only
        )

        response_data = {
            "session_id": session_id,
            "message": result["answer"],
            "sources": search_results if include_sources else [],
            "metadata": {
                "sources_used": result["sources_used"],
                "provider": result["provider"],
                "model": result["model"],
                "history_enabled": result["history_enabled"],
                "query": user_message
            }
        }

        return Response(response_data, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Chat failed for message '{user_message}': {e}")
        return Response(
            {"error": "Chat failed", "detail": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def chat_stats(request):
    """Get statistics about in-memory chat sessions."""
    from apps.chatbot.services.chat_history import get_chat_store_stats

    try:
        stats = get_chat_store_stats()
        return Response({
            "status": "success",
            "stats": stats
        })
    except Exception as e:
        logger.error(f"Failed to get chat stats: {e}")
        return Response(
            {"error": "Failed to get chat statistics", "detail": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Simple health check endpoint for the chatbot service."""
    return Response({
        "status": "healthy",
        "service": "chatbot",
        "version": "1.0"
    })
