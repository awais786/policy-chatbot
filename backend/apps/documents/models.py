"""
Document model for uploaded PDF files.
"""

import logging
import uuid

from django.conf import settings
from django.db import models
from django.db.models import CASCADE, Q, SET_NULL

from apps.core.models import Organization, TimeStampedModel
from apps.documents.services.storage import compute_file_hash, document_upload_path

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
    is_active = models.BooleanField(default=True, help_text="Mark as inactive to hide from normal operations")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    error_message = models.TextField(blank=True, default="")
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
        """Auto-compute file_hash when a new file is attached."""
        file_field = self.file
        if file_field and hasattr(file_field, "chunks"):
            try:
                self.file_hash = compute_file_hash(file_field)
            except Exception:
                logger.exception("Failed to compute file hash for %s", self.title)
        super().save(*args, **kwargs)

    @property
    def is_processed(self) -> bool:
        return self.status == self.Status.COMPLETED

    @property
    def chunk_count(self) -> int:
        try:
            return self.chunks.count()
        except AttributeError:
            return 0
