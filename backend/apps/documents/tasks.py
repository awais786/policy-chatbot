"""
Celery tasks for asynchronous document processing.

The main pipeline: PDF upload → extract text → chunk → embed → store in pgvector.
Triggered automatically after a document is uploaded via the API or admin.
"""

import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def process_document(self, document_id: str) -> dict:
    """
    Full processing pipeline for a single document.

    Steps:
        1. Extract text from PDF
        2. Split text into overlapping chunks
        3. Generate embeddings for each chunk via OpenAI (if API key configured)
        4. Store chunks + embeddings in pgvector
        5. Update document status to COMPLETED

    Args:
        document_id: UUID of the Document to process.

    Returns:
        dict with processing summary.
    """
    try:
        from apps.documents.models import Document, DocumentChunk
        from apps.documents.services.pdf_extractor import (
            PDFExtractionError,
            extract_text_from_file,
        )
        from apps.documents.services.text_chunker import chunk_text
    except Exception as exc:
        logger.exception("Failed to import required modules")
        return {"status": "error", "detail": f"Import error: {exc}"}

    try:
        document = Document.objects.get(pk=document_id)
    except Document.DoesNotExist:
        logger.error("Document %s not found, skipping.", document_id)
        return {"status": "error", "detail": "Document not found"}

    if document.status == Document.Status.COMPLETED:
        logger.info("Document %s already processed, skipping.", document_id)
        return {"status": "skipped", "detail": "Already processed"}


    # Mark as processing
    document.status = Document.Status.PROCESSING
    document.error_message = ""
    document.save(update_fields=["status", "error_message", "updated_at"])

    try:
        # --- Step 1: Extract text from PDF ---
        logger.info("Step 1/4: Extracting text from %s", document.title)

        if not document.file:
            raise PDFExtractionError("No file attached to document.")

        extraction = extract_text_from_file(document.file)
        full_text = extraction["text"]

        if not full_text.strip():
            raise PDFExtractionError("No text could be extracted from the PDF.")

        # Save extracted text and metadata on the document
        document.text_content = full_text
        if not document.metadata:
            document.metadata = {}
        document.metadata["page_count"] = extraction["page_count"]
        document.metadata.update(extraction["metadata"])
        document.save(update_fields=["text_content", "metadata", "updated_at"])

        # --- Step 2: Chunk text and save chunks WITHOUT embeddings ---
        logger.info("Step 2/3: Chunking text (%d chars)", len(full_text))

        chunks = chunk_text(full_text)
        if not chunks:
            raise PDFExtractionError("Text chunking produced no chunks.")

        logger.info("Created %d chunks", len(chunks))

        # --- Step 3: Save chunks to database (without embeddings) ---
        logger.info("Step 3/3: Saving chunks to database")

        # Delete existing chunks for this document (idempotent reprocessing)
        document.chunks.all().delete()

        chunk_objects = []
        for chunk_data in chunks:
            chunk_objects.append(DocumentChunk(
                document=document,
                organization=document.organization,
                content=chunk_data.content,
                chunk_index=chunk_data.chunk_index,
                # embedding=None by default - will be populated later
            ))

        try:
            DocumentChunk.objects.bulk_create(chunk_objects)
            logger.info("Saved %d chunks to database", len(chunk_objects))
        except Exception as exc:
            raise PDFExtractionError(f"Failed to save chunks to database: {exc}")

        # --- Mark document as completed (chunking phase done) ---
        document.status = Document.Status.COMPLETED
        document.processed_at = timezone.now()
        document.save(update_fields=["status", "processed_at", "updated_at"])

        logger.info("Document processing completed: %s", document.title)

        # --- Schedule embedding generation as separate async task ---
        try:
            generate_embeddings_for_document.delay(str(document.id))
            logger.info("Scheduled embedding generation for document: %s", document.title)
        except Exception as exc:
            logger.warning("Failed to schedule embedding generation: %s", exc)
            # Don't fail the main task if embedding scheduling fails

        summary = {
            "status": "completed",
            "document_id": str(document.id),
            "page_count": extraction["page_count"],
            "chunk_count": len(chunk_objects),
            "text_length": len(full_text),
            "embedding_scheduled": True,
        }
        logger.info("Document %s processed successfully: %s", document.title, summary)
        return summary

    except PDFExtractionError as exc:
        logger.error("Document %s processing failed: %s", document_id, exc)
        document.status = Document.Status.FAILED
        document.error_message = str(exc)
        document.save(update_fields=["status", "error_message", "updated_at"])
        return {"status": "failed", "detail": str(exc)}

    except Exception as exc:
        logger.exception("Unexpected error processing document %s", document_id)
        document.status = Document.Status.FAILED
        document.error_message = f"Unexpected error: {exc}"
        document.save(update_fields=["status", "error_message", "updated_at"])
        return {"status": "failed", "detail": str(exc)}


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
    acks_late=True,
)
def generate_embeddings_for_document(self, document_id: str) -> dict:
    """
    Generate embeddings for all chunks of a specific document.

    This task runs separately from document processing, allowing:
    - Faster initial document processing (chunking only)
    - Separate retry logic for embeddings
    - Batch embedding generation
    - Better error handling for embedding failures

    Args:
        document_id: UUID of the Document to generate embeddings for.

    Returns:
        dict with embedding generation summary.
    """
    try:
        from apps.documents.models import Document, DocumentChunk
        from apps.documents.services.embeddings import generate_embeddings, EmbeddingError
    except Exception as exc:
        logger.exception("Failed to import required modules for embedding generation")
        return {"status": "error", "detail": f"Import error: {exc}"}

    try:
        document = Document.objects.get(pk=document_id)
    except Document.DoesNotExist:
        logger.error("Document %s not found for embedding generation", document_id)
        return {"status": "error", "detail": "Document not found"}

    # Get all chunks for this document that don't have embeddings
    chunks_without_embeddings = document.chunks.filter(embedding__isnull=True).order_by('chunk_index')

    if not chunks_without_embeddings.exists():
        logger.info("Document %s already has embeddings for all chunks", document.title)
        return {"status": "skipped", "detail": "All chunks already have embeddings"}

    chunk_count = chunks_without_embeddings.count()
    logger.info("Generating embeddings for %d chunks in document: %s", chunk_count, document.title)

    try:
        # Extract text content from chunks
        chunk_texts = [chunk.content for chunk in chunks_without_embeddings]

        # Generate embeddings in batch
        embeddings = generate_embeddings(chunk_texts)

        if len(embeddings) != len(chunk_texts):
            raise EmbeddingError(f"Expected {len(chunk_texts)} embeddings, got {len(embeddings)}")

        # Update chunks with their embeddings
        chunks_to_update = []
        for chunk, embedding in zip(chunks_without_embeddings, embeddings):
            chunk.embedding = embedding
            chunks_to_update.append(chunk)

        # Batch update chunks with embeddings
        DocumentChunk.objects.bulk_update(chunks_to_update, ['embedding'], batch_size=100)

        logger.info("Successfully generated embeddings for %d chunks in document: %s",
                   len(chunks_to_update), document.title)

        return {
            "status": "completed",
            "document_id": str(document.id),
            "document_title": document.title,
            "embeddings_generated": len(chunks_to_update),
            "total_chunks": document.chunks.count(),
        }

    except EmbeddingError as exc:
        logger.error("Embedding generation failed for document %s: %s", document.title, exc)
        # Retry the task if we haven't exceeded max_retries
        if self.request.retries < self.max_retries:
            logger.info("Retrying embedding generation for document %s (attempt %d/%d)",
                       document.title, self.request.retries + 1, self.max_retries)
            raise self.retry(countdown=self.default_retry_delay, exc=exc)
        else:
            return {
                "status": "failed",
                "document_id": str(document.id),
                "error": str(exc),
                "retries_exhausted": True
            }

    except Exception as exc:
        logger.exception("Unexpected error during embedding generation for document %s", document.title)
        return {
            "status": "error",
            "document_id": str(document.id),
            "error": str(exc)
        }
