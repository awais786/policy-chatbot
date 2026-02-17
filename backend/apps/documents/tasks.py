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

        # --- Step 2: Chunk text ---
        logger.info("Step 2/4: Chunking text (%d chars)", len(full_text))

        chunks = chunk_text(full_text)
        if not chunks:
            raise PDFExtractionError("Text chunking produced no chunks.")

        logger.info("Created %d chunks", len(chunks))

        # --- Step 3: Generate embeddings (skip if OpenAI not configured) ---
        embeddings = [None] * len(chunks)
        openai_key = getattr(settings, "OPENAI_API_KEY", "")

        if openai_key:
            try:
                from apps.documents.services.embeddings import (
                    EmbeddingError,
                    generate_embeddings,
                )

                logger.info("Step 3/4: Generating embeddings for %d chunks", len(chunks))
                chunk_texts = [c.content for c in chunks]
                embeddings = generate_embeddings(chunk_texts)
            except Exception as exc:
                logger.warning(
                    "Embedding generation failed for %s: %s. "
                    "Chunks will be stored without embeddings.",
                    document.title, exc,
                )
        else:
            logger.info(
                "Step 3/4: Skipping embeddings (OPENAI_API_KEY not configured)"
            )

        # --- Step 4: Store chunks + embeddings ---
        logger.info("Step 4/4: Storing chunks in database")

        # Delete existing chunks for this document (idempotent reprocessing)
        document.chunks.all().delete()

        chunk_objects = []
        for chunk_data, embedding in zip(chunks, embeddings):
            chunk_objects.append(DocumentChunk(
                document=document,
                organization=document.organization,
                content=chunk_data.content,
                chunk_index=chunk_data.chunk_index,
                embedding=embedding if embedding else None,
            ))

        try:
            DocumentChunk.objects.bulk_create(chunk_objects)
        except Exception as exc:
            logger.warning("Failed to create some chunks for document %s: %s", document.pk, exc)
            # Continue processing even if some chunks couldn't be created

        # Mark as completed
        document.status = Document.Status.COMPLETED
        document.processed_at = timezone.now()
        document.save(update_fields=["status", "processed_at", "updated_at"])

        summary = {
            "status": "completed",
            "document_id": str(document.id),
            "page_count": extraction["page_count"],
            "chunk_count": len(chunk_objects),
            "text_length": len(full_text),
            "has_embeddings": any(e is not None for e in embeddings),
        }
        logger.info(
            "Document %s processed successfully: %s", document.title, summary
        )
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
