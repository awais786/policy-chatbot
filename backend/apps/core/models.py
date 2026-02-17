"""
Core models — Organization, custom User, and Website.
"""

import hashlib
import secrets
import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models, transaction

from apps.core.managers import OrganizationManager


class TimeStampedModel(models.Model):
    """An abstract base class that provides created_at and updated_at."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Organization(TimeStampedModel):
    """Tenant organization that owns documents and websites."""

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
        """Ensure api_key_hash is kept in sync with api_key."""
        if self.api_key:
            self.api_key_hash = hashlib.sha256(self.api_key.encode()).hexdigest()
        super().save(*args, **kwargs)

    def regenerate_api_key(self):
        """Generate a new API key, set hash, save and return the plain key."""
        new_key = f"pk_{secrets.token_urlsafe(32)}"
        self.api_key = new_key
        self.api_key_hash = hashlib.sha256(new_key.encode()).hexdigest()
        # update_fields keeps DB updates minimal
        self.save(update_fields=["api_key", "api_key_hash", "updated_at"])
        return new_key


class User(AbstractUser, TimeStampedModel):
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
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.VIEWER)

    class Meta:
        db_table = "users"

    def __str__(self):
        return f"{self.username} ({self.organization})"


class Website(TimeStampedModel):
    """A website (domain) belonging to an Organization. An org can have multiple websites."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="websites"
    )
    name = models.CharField(
        max_length=255, blank=True, help_text="Optional display name for the website"
    )
    domain = models.CharField(
        max_length=255, help_text="Primary domain or host for this website (e.g. example.com)"
    )
    url = models.URLField(
        blank=True, null=True, help_text="Optional full URL (e.g. https://example.com)"
    )
    is_primary = models.BooleanField(default=False, help_text="Whether this is the primary website for the org")
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "websites"
        ordering = ["-is_primary", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "domain"], name="unique_org_domain")
        ]

    def __str__(self):
        return f"{self.domain} ({self.organization})"

    def save(self, *args, **kwargs):
        # If marking this website as primary, ensure other websites for the org are not primary
        if self.is_primary:
            # Use an atomic transaction to avoid races
            with transaction.atomic():
                Website.objects.select_for_update().filter(
                    organization=self.organization, is_primary=True
                ).exclude(pk=self.pk).update(is_primary=False)
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)
