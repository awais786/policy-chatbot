"""
Document models — Document and DocumentChunk with pgvector embeddings.
"""

import uuid

from django.conf import settings
from django.db import models
from django.db.models import CASCADE, SET_NULL

from apps.core.models import Organization, TimeStampedModel
from apps.documents.services.storage import compute_file_hash, document_upload_path


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
    file = models.FileField(upload_to=document_upload_path, blank=True, null=True)
    # SHA-256 of the file contents; computed automatically on save when a file is present
    file_hash = models.CharField(max_length=64, db_index=True, blank=True, null=True)
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

    def save(self, *args, **kwargs):
        """Compute file_hash automatically if a file is attached and hash is missing.

        This keeps the admin form simple: `file_hash` is not required and is updated
        by the model when a file is present.
        """
        # Only attempt to compute hash if a file object is present and hash is empty
        try:
            file_field = getattr(self, 'file', None)
        except Exception:
            file_field = None

        if file_field and (not self.file_hash):
            # Some file representations support .chunks(); guard accordingly
            if hasattr(file_field, 'chunks'):
                try:
                    self.file_hash = compute_file_hash(file_field)
                except Exception:
                    # If hashing fails for any reason, leave file_hash blank and proceed
                    self.file_hash = None

        super().save(*args, **kwargs)

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
