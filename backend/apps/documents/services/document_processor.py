"""
Unified document processing service.

This service provides a single entry point for document processing that can be used
from admin, management commands, API views, or anywhere else in the application.

The processing pipeline:
1. Extract text from PDF
2. Chunk text with enhanced processing
3. Generate embeddings
4. Store everything in database
"""

import logging
from typing import Dict, Any, Optional
from django.db import transaction
from django.utils import timezone

from apps.documents.models import Document, DocumentChunk
from apps.documents.services.pdf_extractor import extract_text_from_file, PDFExtractionError
from apps.documents.services.text_chunker import chunk_text
from apps.documents.services.embeddings import generate_embeddings, EmbeddingError

logger = logging.getLogger(__name__)


class DocumentProcessingError(Exception):
    """Raised when document processing fails."""
    pass


class DocumentProcessor:
    """
    Unified document processing service.

    Handles the complete pipeline: PDF extraction → text chunking → embedding generation.
    Can be used synchronously or asynchronously.
    """

    def __init__(self, document: Document):
        self.document = document
        self.logger = logging.getLogger(f"{__name__}.{document.pk}")

    def process(self, chunk_size: int = 1000, chunk_overlap: int = 200) -> Dict[str, Any]:
        """
        Process a document through the complete pipeline.

        Args:
            chunk_size: Size of text chunks
            chunk_overlap: Overlap between chunks

        Returns:
            Dict with processing results and statistics

        Raises:
            DocumentProcessingError: If processing fails
        """
        try:
            self.logger.info(f"Starting processing for document: {self.document.title}")

            # Step 1: Extract text from PDF
            extraction_result = self._extract_text()
            full_text = extraction_result['text']

            # Step 2: Chunk the text
            chunks = self._chunk_text(full_text, chunk_size, chunk_overlap)

            # Step 3: Generate embeddings
            embeddings = self._generate_embeddings(chunks)

            # Step 4: Save everything to database
            result = self._save_chunks_and_embeddings(chunks, embeddings, extraction_result)

            self.logger.info(f"Successfully processed document: {self.document.title}")
            return result

        except Exception as e:
            error_msg = f"Failed to process document {self.document.title}: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            raise DocumentProcessingError(error_msg) from e

    def _extract_text(self) -> Dict[str, Any]:
        """Extract text from the PDF file."""
        if not self.document.file:
            raise DocumentProcessingError("Document has no file attached")

        try:
            extraction_result = extract_text_from_file(self.document.file)
            self.logger.info(f"Extracted {len(extraction_result['text'])} characters from PDF")
            return extraction_result
        except PDFExtractionError as e:
            raise DocumentProcessingError(f"PDF extraction failed: {e}") from e

    def _chunk_text(self, text: str, chunk_size: int, chunk_overlap: int) -> list:
        """Chunk the extracted text."""
        try:
            chunks = chunk_text(
                text,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                preserve_sentences=True
            )
            self.logger.info(f"Created {len(chunks)} text chunks")
            return chunks
        except Exception as e:
            raise DocumentProcessingError(f"Text chunking failed: {e}") from e

    def _generate_embeddings(self, chunks: list) -> list:
        """Generate embeddings for all chunks."""
        if not chunks:
            return []

        try:
            chunk_texts = [chunk.content for chunk in chunks]
            embeddings = generate_embeddings(chunk_texts)
            self.logger.info(f"Generated {len(embeddings)} embeddings")
            return embeddings
        except EmbeddingError as e:
            raise DocumentProcessingError(f"Embedding generation failed: {e}") from e

    def _save_chunks_and_embeddings(self, chunks: list, embeddings: list, extraction_result: Dict[str, Any]) -> Dict[str, Any]:
        """Save chunks and embeddings to database."""
        with transaction.atomic():
            # Delete existing chunks
            existing_count = self.document.chunks.count()
            if existing_count > 0:
                self.document.chunks.all().delete()
                self.logger.info(f"Deleted {existing_count} existing chunks")

            # Create new chunks
            chunk_objects = []
            for i, chunk_data in enumerate(chunks):
                embedding = embeddings[i] if i < len(embeddings) else None

                chunk_objects.append(DocumentChunk(
                    document=self.document,
                    organization=self.document.organization,
                    content=chunk_data.content,
                    chunk_index=i,
                    metadata=chunk_data.metadata,
                    embedding=embedding
                ))

            # Bulk create chunks
            DocumentChunk.objects.bulk_create(chunk_objects)

            # Update document
            self.document.text_content = extraction_result['text']
            self.document.metadata.update(extraction_result.get('metadata', {}))
            self.document.status = Document.Status.COMPLETED
            self.document.error_message = ""
            self.document.processed_at = timezone.now()
            self.document.save(update_fields=[
                'text_content', 'metadata', 'status', 'error_message', 'processed_at'
            ])

            return {
                'document_id': str(self.document.pk),
                'chunks_created': len(chunk_objects),
                'embeddings_generated': len([e for e in embeddings if e is not None]),
                'text_length': len(extraction_result['text']),
                'processing_time': None  # Could add timing if needed
            }


def process_document(document: Document, chunk_size: int = 1000, chunk_overlap: int = 200) -> Dict[str, Any]:
    """
    Convenience function to process a document using the unified processor.

    Args:
        document: Document instance to process
        chunk_size: Size of text chunks
        chunk_overlap: Overlap between chunks

    Returns:
        Dict with processing results
    """
    processor = DocumentProcessor(document)
    return processor.process(chunk_size=chunk_size, chunk_overlap=chunk_overlap)


def process_document_by_id(document_id: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> Dict[str, Any]:
    """
    Process a document by its ID.

    Args:
        document_id: UUID string of the document
        chunk_size: Size of text chunks
        chunk_overlap: Overlap between chunks

    Returns:
        Dict with processing results

    Raises:
        DocumentProcessingError: If document not found or processing fails
    """
    try:
        document = Document.objects.get(pk=document_id)
    except Document.DoesNotExist:
        raise DocumentProcessingError(f"Document with ID {document_id} not found")

    return process_document(document, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
