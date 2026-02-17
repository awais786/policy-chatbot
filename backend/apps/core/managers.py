"""
Custom model managers for core models.
"""

import secrets

from django.db import models


class OrganizationManager(models.Manager):
    """Custom manager for Organization model."""

    def create_organization(self, name, slug=None):
        """Create organization with auto-generated API key.

        Args:
            name: The organization display name.
            slug: URL-safe slug (auto-generated from name if omitted).

        Returns:
            The newly created Organization instance.
        """
        if not slug:
            slug = name.lower().replace(' ', '-')

        api_key = f"pk_{secrets.token_urlsafe(32)}"

        return self.create(
            name=name,
            slug=slug,
            api_key=api_key,
        )
