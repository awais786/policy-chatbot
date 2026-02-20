"""
Vector search service using pgvector for semantic document search.

This service handles:
- Embedding user queries
- Performing similarity search against document chunks
- Ranking and filtering results
"""

import logging
import math
from typing import List, Dict, Any, Optional

from django.conf import settings
from django.db import connection

from apps.documents.models import DocumentChunk
from apps.documents.services.embeddings import generate_single_embedding

logger = logging.getLogger(__name__)

MAX_QUERY_LENGTH = 2000
MAX_SEARCH_LIMIT = 50


def _validate_embedding(embedding: List[float]) -> None:
    """Validate that embedding contains only finite numeric values."""
    if not embedding:
        raise ValueError("Empty embedding returned from embedding service")

    expected_dim = int(getattr(settings, "EMBEDDING_DIMENSIONS", 0) or 0)
    if expected_dim and len(embedding) != expected_dim:
        raise ValueError(
            f"Embedding dimension mismatch: expected {expected_dim}, got {len(embedding)}"
        )

    for i, val in enumerate(embedding):
        if not isinstance(val, (int, float)):
            raise ValueError(f"Non-numeric value at embedding index {i}")
        if not math.isfinite(float(val)):
            raise ValueError(f"Non-finite value at embedding index {i}")


class VectorSearchService:
    """Service for performing semantic search on document chunks using pgvector."""

    def __init__(self, organization_id: str):
        self.organization_id = organization_id

    def search(
        self,
        query: str,
        limit: int = 10,
        min_similarity: float = 0.7,
        document_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search on document chunks.

        Args:
            query: Search query text
            limit: Maximum number of results to return
            min_similarity: Minimum cosine similarity threshold (0.0 to 1.0)
            document_ids: Optional list of document IDs to restrict search to

        Returns:
            List of search results with similarity scores
        """
        if not query or not query.strip():
            raise ValueError("Search query cannot be empty")

        if len(query) > MAX_QUERY_LENGTH:
            raise ValueError(
                f"Query exceeds maximum length of {MAX_QUERY_LENGTH} characters"
            )

        limit = max(1, min(limit, MAX_SEARCH_LIMIT))
        min_similarity = max(0.0, min(min_similarity, 1.0))

        try:
            query_embedding = generate_single_embedding(query)

            _validate_embedding(query_embedding)

            logger.info(
                "Vector search: query_length=%d, embedding_dims=%d, limit=%d, min_similarity=%.2f",
                len(query), len(query_embedding), limit, min_similarity,
            )

            results = self._vector_similarity_search(
                query_embedding=query_embedding,
                limit=limit,
                min_similarity=min_similarity,
                document_ids=document_ids,
            )

            logger.info(
                "Vector search completed: results=%d, query_preview=%s",
                len(results), query[:50],
            )
            return results

        except ValueError:
            raise
        except Exception as e:
            logger.error("Vector search failed: %s", type(e).__name__)
            raise

    def _vector_similarity_search(
        self,
        query_embedding: List[float],
        limit: int,
        min_similarity: float,
        document_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Perform the actual vector similarity search using raw SQL with pgvector.

        All parameters are passed through Django's parameterized query mechanism
        to prevent SQL injection.
        """
        embedding_str = "[" + ",".join(str(float(v)) for v in query_embedding) + "]"

        params: list = [
            embedding_str,
            str(self.organization_id),
        ]

        document_filter = ""
        if document_ids:
            placeholders = ",".join(["%s"] * len(document_ids))
            document_filter = f"AND dc.document_id IN ({placeholders})"
            params.extend(str(did) for did in document_ids)

        params.extend([
            embedding_str,
            min_similarity,
            embedding_str,
            limit,
        ])

        sql = f"""
        SELECT
            dc.id,
            dc.document_id,
            dc.chunk_index,
            dc.content,
            d.title as document_title,
            (1 - (dc.embedding <=> %s::vector)) as similarity_score
        FROM document_chunks dc
        INNER JOIN documents d ON dc.document_id = d.id
        WHERE
            dc.organization_id = %s
            AND dc.embedding IS NOT NULL
            AND d.is_active = true
            {document_filter}
            AND (1 - (dc.embedding <=> %s::vector)) >= %s
        ORDER BY dc.embedding <=> %s::vector
        LIMIT %s;
        """

        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            columns = [col[0] for col in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

        import json as _json
        for row in rows:
            title = (row.get("document_title") or "").strip()
            content = (row.get("content") or "").strip()

            # Drop document_metadata from response (internal use only)
            row.pop("document_metadata", None)

            # Prefix every chunk with [Document: title] so the LLM
            # always knows which document/person this chunk belongs to
            if title:
                row["content"] = f"[Document: {title}]\n{content}"
            else:
                row["content"] = content

        return rows

    def search_by_document(
        self,
        query: str,
        document_id: str,
        limit: int = 5,
        min_similarity: float = 0.6,
    ) -> List[Dict[str, Any]]:
        """Search within a specific document only."""
        return self.search(
            query=query,
            limit=limit,
            min_similarity=min_similarity,
            document_ids=[document_id],
        )

    def get_similar_chunks(
        self,
        chunk_id: str,
        limit: int = 5,
        min_similarity: float = 0.8,
    ) -> List[Dict[str, Any]]:
        """Find chunks similar to a given chunk (\"more like this\")."""
        try:
            chunk = DocumentChunk.objects.get(
                id=chunk_id,
                organization_id=self.organization_id,
            )

            if not chunk.embedding:
                raise ValueError("Reference chunk has no embedding")

            return self._vector_similarity_search(
                query_embedding=chunk.embedding,
                limit=limit,
                min_similarity=min_similarity,
            )

        except DocumentChunk.DoesNotExist:
            logger.warning("Chunk not found for similar-chunk search")
            return []
