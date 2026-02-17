"""
Document models — Document and DocumentChunk with pgvector embeddings.
"""

import uuid

from django.conf import settings
from django.db import models
from django.db.models import CASCADE, SET_NULL

from apps.core.models import Organization, TimeStampedModel
from apps.documents.services.storage import document_upload_path


class DocumentManager(models.Manager):
    def for_organization(self, organization):
        return self.filter(organization=organization)

    def completed(self):
        return self.filter(status=Document.Status.COMPLETED)


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
    file = models.FileField(upload_to=document_upload_path)
    file_hash = models.CharField(max_length=64, db_index=True)  # SHA-256
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    error_message = models.TextField(blank=True, null=True)
    metadata = models.JSONField(
        default=dict, blank=True
    )  # original_filename, file_size, page_count, mime_type
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
            ),
        ]

    def __str__(self):
        return self.title

    @property
    def is_processed(self) -> bool:
        return self.status == Document.Status.COMPLETED

    @property
    def chunk_count(self) -> int:
        return self.chunks.count()
