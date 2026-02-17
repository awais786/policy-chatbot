"""
Core models — Organization and custom User.
"""

import hashlib
import secrets
import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.core.managers import OrganizationManager


class Organization(models.Model):
    """Tenant organization that owns documents."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, max_length=255)
    api_key = models.CharField(max_length=100, unique=True, db_index=True)
    api_key_hash = models.CharField(max_length=64, editable=False)
    is_active = models.BooleanField(default=True)
    settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="Widget customisation, LLM config, search config, limits.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = OrganizationManager()

    class Meta:
        db_table = "organizations"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["api_key"], name="idx_org_api_key"),
            models.Index(fields=["slug"], name="idx_org_slug"),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Hash the api_key with SHA-256 before persisting."""
        if self.api_key:
            self.api_key_hash = hashlib.sha256(
                self.api_key.encode()
            ).hexdigest()
        super().save(*args, **kwargs)

    def regenerate_api_key(self):
        """Generate a new API key, hash it, save, and return the new key."""
        new_key = f"pk_{secrets.token_urlsafe(32)}"
        self.api_key = new_key
        self.api_key_hash = hashlib.sha256(new_key.encode()).hexdigest()
        self.save(update_fields=["api_key", "api_key_hash", "updated_at"])
        return new_key


class User(AbstractUser):
    """Custom user model linked to an Organization."""

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        EDITOR = "editor", "Editor"
        VIEWER = "viewer", "Viewer"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="users",
        null=True,
        blank=True,
    )
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.VIEWER,
    )

    class Meta:
        db_table = "users"

    def __str__(self):
        return f"{self.username} ({self.organization})"
