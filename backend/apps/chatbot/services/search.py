"""
Vector search service using pgvector for semantic document search.

This service handles:
- Embedding user queries
- Performing similarity search against document chunks
- Ranking and filtering results
"""

import logging
from typing import List, Dict, Any

from django.db import connection
from apps.documents.models import DocumentChunk
from apps.documents.services.embeddings import generate_single_embedding

logger = logging.getLogger(__name__)


class VectorSearchService:
    """Service for performing semantic search on document chunks using pgvector."""

    def __init__(self, organization_id: str):
        self.organization_id = organization_id

    def search(
        self,
        query: str,
        limit: int = 10,
        min_similarity: float = 0.7,
        document_ids: List[str] = None,
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
        try:
            # Generate embedding for the search query
            logger.info(f"Generating embedding for query: {query[:50]}...")
            query_embedding = generate_single_embedding(query)

            # Build the base queryset
            queryset = DocumentChunk.objects.filter(
                organization_id=self.organization_id,
                embedding__isnull=False,  # Only chunks with embeddings
                document__is_active=True,  # Only active documents
            ).select_related('document')

            # Filter by specific documents if provided
            if document_ids:
                queryset = queryset.filter(document_id__in=document_ids)

            # Perform vector similarity search using pgvector
            results = self._vector_similarity_search(
                queryset=queryset,
                query_embedding=query_embedding,
                limit=limit,
                min_similarity=min_similarity
            )

            logger.info(f"Found {len(results)} results for query: {query[:50]}")
            return results

        except Exception as e:
            logger.error(f"Vector search failed for query '{query}': {e}")
            raise

    def _vector_similarity_search(
        self,
        queryset,
        query_embedding: List[float],
        limit: int,
        min_similarity: float
    ) -> List[Dict[str, Any]]:
        """
        Perform the actual vector similarity search using raw SQL.

        Uses pgvector's cosine similarity operator for efficient search.
        """
        # Convert embedding to pgvector format
        embedding_str = f"[{','.join(map(str, query_embedding))}]"

        # Raw SQL for pgvector cosine similarity search
        sql = """
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
            AND (1 - (dc.embedding <=> %s::vector)) >= %s
        ORDER BY dc.embedding <=> %s::vector
        LIMIT %s;
        """

        with connection.cursor() as cursor:
            cursor.execute(sql, [
                embedding_str,  # query embedding for similarity calculation
                self.organization_id,  # organization filter
                embedding_str,  # query embedding for threshold check
                min_similarity,  # minimum similarity threshold
                embedding_str,  # query embedding for ordering
                limit  # result limit
            ])

            columns = [col[0] for col in cursor.description]
            results = []

            for row in cursor.fetchall():
                result_dict = dict(zip(columns, row))
                results.append(result_dict)

        return results

    def search_by_document(
        self,
        query: str,
        document_id: str,
        limit: int = 5,
        min_similarity: float = 0.6
    ) -> List[Dict[str, Any]]:
        """
        Search within a specific document only.

        Useful for finding relevant sections within a particular document.
        """
        return self.search(
            query=query,
            limit=limit,
            min_similarity=min_similarity,
            document_ids=[document_id]
        )

    def get_similar_chunks(
        self,
        chunk_id: str,
        limit: int = 5,
        min_similarity: float = 0.8
    ) -> List[Dict[str, Any]]:
        """
        Find chunks similar to a given chunk.

        Useful for "more like this" functionality.
        """
        try:
            # Get the reference chunk
            chunk = DocumentChunk.objects.get(
                id=chunk_id,
                organization_id=self.organization_id
            )

            if not chunk.embedding:
                raise ValueError(f"Chunk {chunk_id} has no embedding")

            # Use the chunk's embedding as the query
            return self._vector_similarity_search(
                queryset=DocumentChunk.objects.filter(
                    organization_id=self.organization_id,
                    embedding__isnull=False
                ).exclude(id=chunk_id),  # Exclude the reference chunk itself
                query_embedding=chunk.embedding,
                limit=limit,
                min_similarity=min_similarity
            )

        except DocumentChunk.DoesNotExist:
            logger.error(f"Chunk {chunk_id} not found")
            return []
