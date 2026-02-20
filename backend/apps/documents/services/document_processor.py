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
from apps.documents.services.pdf_extractor import extract_text_from_file, PDFExtractionError, extract_title_from_pdf_text
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

    def process(self, chunk_size: int = None, chunk_overlap: int = None) -> Dict[str, Any]:
        """
        Process a document through the complete pipeline.

        Args:
            chunk_size: Size of text chunks (defaults to settings.CHUNK_SIZE)
            chunk_overlap: Overlap between chunks (defaults to settings.CHUNK_OVERLAP)

        Returns:
            Dict with processing results and statistics

        Raises:
            DocumentProcessingError: If processing fails
        """
        from django.conf import settings as django_settings
        chunk_size = chunk_size or int(getattr(django_settings, 'CHUNK_SIZE', 500))
        chunk_overlap = chunk_overlap or int(getattr(django_settings, 'CHUNK_OVERLAP', 100))
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
        """Extract text from the PDF file, or fall back to stored text_content."""
        # If no file, use already-stored text_content
        if not self.document.file:
            text = getattr(self.document, 'text_content', '') or ''
            if not text.strip():
                raise DocumentProcessingError("Document has no file attached and no text_content stored")
            self.logger.info(f"No file attached; using stored text_content ({len(text)} chars)")
            return {'text': text, 'pages': 0, 'method': 'text_content'}

        try:
            extraction_result = extract_text_from_file(self.document.file)
            self.logger.info(f"Extracted {len(extraction_result['text'])} characters from PDF")

            # Auto-update title from PDF content if current title looks like
            # a raw filename, gibberish, or is very short (e.g. "ioi", "sad", "asdasd")
            self._maybe_update_title_from_pdf(extraction_result)

            return extraction_result
        except PDFExtractionError as e:
            raise DocumentProcessingError(f"PDF extraction failed: {e}") from e

    def _maybe_update_title_from_pdf(self, extraction_result: Dict[str, Any]) -> None:
        """
        If the document title looks like a raw filename or gibberish,
        try to derive a better title from the PDF metadata or extracted text.
        """
        current_title = (self.document.title or "").strip()

        # Derive the filename stem for comparison
        filename_stem = ""
        if self.document.file and self.document.file.name:
            import os
            filename_stem = os.path.splitext(
                os.path.basename(self.document.file.name)
            )[0].lower().replace("_", " ").replace("-", " ")

        # Heuristics: title looks like a filename/gibberish when:
        #   - it has no spaces (single token like "ioi", "asdasd")
        #   - it's very short (≤ 8 chars)
        #   - it matches the filename stem exactly
        title_words = current_title.split()
        looks_like_garbage = (
            len(title_words) <= 1
            or len(current_title) <= 8
            or current_title.lower() == filename_stem
        )

        if not looks_like_garbage:
            return  # Title is already meaningful, leave it alone

        # Try to extract a meaningful title
        suggested = extract_title_from_pdf_text(
            extraction_result.get("metadata", {}),
            extraction_result.get("text", ""),
        )

        if suggested and suggested.strip() and suggested.strip() != current_title:
            self.logger.info(
                "Auto-updating title from %r → %r", current_title, suggested.strip()
            )
            self.document.title = suggested.strip()
            self.document.save(update_fields=["title"])

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
        """Generate embeddings for all chunks, prefixed with document title."""
        if not chunks:
            return []

        try:
            title = (self.document.title or "").strip()
            # Prefix each chunk with the document title so embeddings capture
            # the document identity (e.g. "Fatima Imran CV\nKiwi Creations...")
            if title:
                chunk_texts = [f"{title}\n{chunk.content}" for chunk in chunks]
            else:
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

            # Store document title as header_context so search can prepend it
            # to all chunks — the title is the clearest identifier (e.g. "Fatima Imran CV")
            header_context = self.document.title.strip() if self.document.title else ""

            # Update document
            self.document.text_content = extraction_result['text']
            meta = dict(self.document.metadata or {})
            meta.update(extraction_result.get('metadata', {}))
            meta['header_context'] = header_context
            self.document.metadata = meta
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


def process_document(document: Document, chunk_size: int = None, chunk_overlap: int = None) -> Dict[str, Any]:
    """
    Convenience function to process a document using the unified processor.

    Args:
        document: Document instance to process
        chunk_size: Size of text chunks (defaults to settings.CHUNK_SIZE)
        chunk_overlap: Overlap between chunks (defaults to settings.CHUNK_OVERLAP)

    Returns:
        Dict with processing results
    """
    processor = DocumentProcessor(document)
    return processor.process(chunk_size=chunk_size, chunk_overlap=chunk_overlap)


def process_document_by_id(document_id: str, chunk_size: int = None, chunk_overlap: int = None) -> Dict[str, Any]:
    """
    Process a document by its ID.

    Args:
        document_id: UUID string of the document
        chunk_size: Size of text chunks (defaults to settings.CHUNK_SIZE)
        chunk_overlap: Overlap between chunks (defaults to settings.CHUNK_OVERLAP)

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
