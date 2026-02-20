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
from apps.chatbot.services.chat_history import get_chat_store_stats, get_recent_messages
from apps.chatbot.services.providers import create_rag_chatbot
from apps.chatbot.services.search import VectorSearchService
from apps.documents.models import Document

logger = logging.getLogger(__name__)

# Keywords that indicate the user is asking about documents themselves
_META_KEYWORDS = (
    "how many", "list", "available", "what document", "which document",
    "what cv", "which cv", "what files", "show me", "do you have",
    "what do you know", "what topics", "what categories",
)


def _get_organization_id(request, data=None) -> str:
    if data and "organization_id" in data:
        return str(data["organization_id"])
    org = getattr(request, "organization", None)
    if org is not None:
        return str(org.id)
    default_org = getattr(settings, "DEFAULT_ORGANIZATION_ID", None)
    if default_org:
        return str(default_org)
    raise ValueError("No organization resolved. Set DEFAULT_ORGANIZATION_ID in settings.")


def _build_document_list_context(organization_id: str) -> str:
    """Build a context string listing all available documents for the org."""
    docs = Document.objects.filter(
        organization_id=organization_id,
        is_active=True,
        status=Document.Status.COMPLETED,
    ).order_by("category", "title")

    if not docs.exists():
        return ""

    lines = ["Available documents in this organization:"]
    by_category: dict = {}
    for doc in docs:
        cat = doc.get_category_display()
        by_category.setdefault(cat, []).append(doc.title)

    for cat, titles in sorted(by_category.items()):
        lines.append(f"\n{cat} ({len(titles)}):")
        for t in titles:
            lines.append(f"  - {t}")

    lines.append(f"\nTotal: {docs.count()} document(s)")
    return "\n".join(lines)


def _is_meta_question(question: str) -> bool:
    """Return True if the question is about what documents are available."""
    q = question.lower()
    return any(kw in q for kw in _META_KEYWORDS)


# Short vague follow-up phrases that need context from history to search well
_VAGUE_FOLLOWUPS = (
    "give me details", "tell me more", "explain", "elaborate", "more details",
    "more information", "what else", "and?", "continue", "go on", "expand",
    "can you explain", "please explain", "what does that mean", "details please",
    "more", "detail", "summarize", "summary", "full details", "everything",
)


def _is_vague_followup(question: str) -> bool:
    """Return True if the question is too vague to search on its own."""
    q = question.lower().strip().rstrip("?.")
    return q in _VAGUE_FOLLOWUPS or any(q.startswith(v) for v in _VAGUE_FOLLOWUPS)


def _expand_query_from_history(question: str, session_id: str) -> str:
    """
    Build a richer search query by prepending the most recent human
    message topic from history.

    e.g.  history: "what is non-compete policy?"
          current: "give me details"
          result:  "non-compete policy details"
    """
    recent = get_recent_messages(session_id, count=6)
    # Walk backwards through history to find the last meaningful user question
    for msg in reversed(recent):
        if msg["type"] == "user":
            prev = msg["content"].strip()
            # Skip if it's also vague
            if _is_vague_followup(prev):
                continue
            # Combine: previous topic + current intent
            expanded = f"{prev} {question}"
            logger.debug("Expanded query: %r -> %r", question, expanded)
            return expanded
    return question


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
    limit = serializer.validated_data.get("limit", getattr(settings, "DEFAULT_TOP_K", 10))
    min_similarity = serializer.validated_data.get(
        "min_similarity", getattr(settings, "DEFAULT_SIMILARITY_THRESHOLD", 0.3)
    )
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
    top_k = int(getattr(settings, "DEFAULT_TOP_K", 10) or 10)
    min_similarity = float(getattr(settings, "DEFAULT_SIMILARITY_THRESHOLD", 0.3) or 0.3)

    try:
        # For meta-questions about documents, inject the document list as context
        if _is_meta_question(user_message):
            doc_list_context = _build_document_list_context(organization_id)
            if doc_list_context:
                search_results = [{
                    "id": "meta",
                    "document_id": "meta",
                    "chunk_index": 0,
                    "content": doc_list_context,
                    "document_title": "Document Index",
                    "similarity_score": 1.0,
                }]
                chatbot = create_rag_chatbot(organization_id)
                result = chatbot.generate_answer(user_message, search_results, session_id)
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

        # Expand vague follow-up queries ("give me details", "tell me more", etc.)
        # using the most recent meaningful question from history
        search_query = user_message
        if _is_vague_followup(user_message):
            search_query = _expand_query_from_history(user_message, session_id)
            logger.debug("Vague follow-up detected. Using expanded query: %r", search_query)

        search_service = VectorSearchService(organization_id)
        search_results = search_service.search(
            query=search_query,
            limit=top_k,
            min_similarity=min_similarity,
        )

        # If expanded query still returns nothing, retry with lower threshold
        if not search_results and search_query != user_message:
            search_results = search_service.search(
                query=search_query,
                limit=top_k,
                min_similarity=max(0.1, min_similarity - 0.1),
            )

        chatbot = create_rag_chatbot(organization_id)
        result = chatbot.generate_answer(user_message, search_results, session_id)

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
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception:
        logger.exception("Chat failed")
        return Response(
            {"error": "An internal error occurred while processing your message."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def list_documents(request):
    """
    List all active documents for an organization, grouped by category.

    GET /api/v1/chat/documents/?organization_id=<uuid>
    POST /api/v1/chat/documents/  { "organization_id": "<uuid>" }
    """
    try:
        organization_id = _get_organization_id(
            request, request.data if request.method == "POST" else request.query_params
        )
    except ValueError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    docs = Document.objects.filter(
        organization_id=organization_id,
        is_active=True,
        status=Document.Status.COMPLETED,
    ).order_by("category", "title")

    by_category: dict = {}
    for doc in docs:
        cat_key = doc.category
        cat_label = doc.get_category_display()
        if cat_key not in by_category:
            by_category[cat_key] = {"label": cat_label, "documents": []}
        by_category[cat_key]["documents"].append({
            "id": str(doc.id),
            "title": doc.title,
            "category": cat_key,
            "category_label": cat_label,
        })

    return Response({
        "organization_id": organization_id,
        "total": docs.count(),
        "categories": by_category,
    }, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([AllowAny])
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
