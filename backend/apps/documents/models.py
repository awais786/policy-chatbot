"""
Document model for uploaded PDF files.

Text extraction, chunking, and embedding generation are handled
asynchronously by the Celery task `process_document` — NOT in save().
"""

import logging
import uuid

from django.conf import settings
from django.db import models
from django.db.models import CASCADE, Q, SET_NULL

from apps.core.models import Organization, TimeStampedModel
from apps.documents.services.storage import compute_file_hash, document_upload_path
from pgvector.django import VectorField


logger = logging.getLogger(__name__)


class DocumentManager(models.Manager):
    def for_organization(self, organization):
        return self.filter(organization=organization)

    def completed(self):
        return self.filter(status=Document.Status.COMPLETED)

    def active(self):
        """Return only active documents."""
        return self.filter(is_active=True)


class Document(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=CASCADE, related_name="documents"
    )
    title = models.CharField(max_length=500)
    file = models.FileField(upload_to=document_upload_path, blank=True, null=True)
    file_hash = models.CharField(
        max_length=64, db_index=True, blank=True, default=""
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Mark as inactive to hide from normal operations",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    error_message = models.TextField(blank=True, default="")
    text_content = models.TextField(
        blank=True, default="",
        help_text="Extracted text from the PDF file (populated by async task)",
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_documents",
    )
    processed_at = models.DateTimeField(null=True, blank=True)

    objects = DocumentManager()

    class Meta:
        db_table = "documents"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["organization", "status"],
                name="idx_doc_org_status",
            ),
            models.Index(
                fields=["organization", "created_at"],
                name="idx_doc_org_created",
            ),
            models.Index(fields=["file_hash"], name="idx_doc_file_hash"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "file_hash"],
                name="unique_document_per_org",
                condition=Q(file_hash__gt=""),
            ),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        """
        Compute file_hash on new uploads. Text extraction and embedding
        generation are handled asynchronously — see tasks.process_document.
        """
        if self.file and hasattr(self.file, "chunks"):
            try:
                self.file_hash = compute_file_hash(self.file)
            except Exception:
                logger.exception("Failed to compute file hash for %s", self.title)

        try:
            super().save(*args, **kwargs)
        except Exception as exc:
            if "unique_document_per_org" in str(exc) and self.file_hash:
                import time
                self.file_hash = f"{self.file_hash}_{int(time.time())}"
                logger.info(
                    "Duplicate hash for %s, using unique variant: %s",
                    self.title, self.file_hash,
                )
                super().save(*args, **kwargs)
            else:
                raise

    def schedule_processing(self):
        """
        Dispatch the async processing pipeline (extract → chunk → embed).

        Call this after a document is successfully saved with a file attached.
        In development (CELERY_TASK_ALWAYS_EAGER=True) this runs synchronously.
        """
        from apps.documents.tasks import process_document

        process_document.delay(str(self.pk))
        logger.info("Scheduled processing for document %s (%s)", self.title, self.pk)

    @property
    def is_processed(self) -> bool:
        return self.status == self.Status.COMPLETED

    @property
    def chunk_count(self) -> int:
        """Return the number of text chunks for this document."""
        return self.chunks.count()


class DocumentChunk(TimeStampedModel):
    """Text chunks from documents with vector embeddings for semantic search."""

    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name="chunks",
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="document_chunks",
    )
    content = models.TextField()
    chunk_index = models.IntegerField()
    embedding = VectorField(dimensions=1536, null=True, blank=True)

    class Meta:
        db_table = "document_chunks"
        ordering = ["document", "chunk_index"]
        indexes = [
            models.Index(
                fields=["document", "chunk_index"], name="idx_chunk_doc_index",
            ),
            models.Index(fields=["organization"], name="idx_chunk_org"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "chunk_index"], name="unique_chunk_per_doc",
            )
        ]

    def __str__(self):
        return f"{self.document.title} - Chunk {self.chunk_index}"