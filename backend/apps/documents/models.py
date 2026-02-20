"""
Document model for uploaded PDF files.

Text extraction, chunking, and embedding generation are handled
asynchronously by the Celery task `process_document` — NOT in save().
"""

import logging
import uuid

from typing import Any, Dict

from django.conf import settings
from django.db import models
from django.db.models import CASCADE, SET_NULL
from django.db.models.signals import post_save
from django.dispatch import receiver

# Import moved to avoid circular imports - will be imported when needed
# from apps.documents.tasks import process_document

from apps.core.models import Organization, TimeStampedModel
from apps.documents.services.storage import document_upload_path
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

    class Category(models.TextChoices):
        GENERAL = "general", "General"
        HR = "hr", "HR"
        FINANCE = "finance", "Finance"
        POLICY = "policy", "Policy"
        CV = "cv", "CV / Resume"
        LEGAL = "legal", "Legal"
        TECHNICAL = "technical", "Technical"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=CASCADE, related_name="documents"
    )
    title = models.CharField(max_length=500)
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.GENERAL,
        db_index=True,
        help_text="Document category for filtering and context",
    )
    file = models.FileField(upload_to=document_upload_path, blank=True, null=True)
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
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        """
        Basic save method. Text extraction and embedding generation
        are handled asynchronously — see tasks.process_document.
        """
        super().save(*args, **kwargs)

    def schedule_processing(self):
        """
        Dispatch the async processing pipeline (extract → chunk → embed).

        Call this after a document is successfully saved with a file attached.
        In development (CELERY_TASK_ALWAYS_EAGER=True) this runs synchronously.
        """
        try:
            # Import here to avoid circular imports (tasks.py imports models.py)
            from apps.documents.tasks import process_document
            process_document.delay(str(self.pk))
            logger.info("Scheduled processing for document %s (%s)", self.title, self.pk)
        except Exception as e:
            logger.error(f"Failed to schedule processing for document {self.title}: {e}", exc_info=True)

    def process_document(self, chunk_size: int = 1000, chunk_overlap: int = 200) -> Dict[str, Any]:
        """
        Process this document using the unified processing pipeline.

        This method can be called from admin, API views, or anywhere else
        to trigger document processing synchronously.

        Args:
            chunk_size: Size of text chunks
            chunk_overlap: Overlap between chunks

        Returns:
            Dict with processing results
        """
        from apps.documents.services.document_processor import process_document
        return process_document(self, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

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
    embedding = VectorField(dimensions=getattr(settings, 'EMBEDDING_DIMENSIONS', 1536), null=True, blank=True)
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Chunk metadata: char positions, word count, section info, etc."
    )

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

@receiver(post_save, sender=Document)
def auto_schedule_processing(sender, instance, created, **kwargs):
    """
    Automatically schedule processing when a document is saved with a file
    and is still in PENDING status. Works from admin, API, shell, etc.

    The task itself guards against double-processing (skips if already
    COMPLETED), so even if this fires more than once it's safe.
    """
    if not (instance.file and instance.status == Document.Status.PENDING):
        return

    if not (hasattr(instance.file, "name") and instance.file.name):
        return

    instance.schedule_processing()
