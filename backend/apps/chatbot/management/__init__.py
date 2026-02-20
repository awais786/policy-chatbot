"""
Shared utilities for chatbot management commands.
"""
import uuid as _uuid

from apps.core.models import Organization


def resolve_organization_id(value: str) -> str:
    """Resolve an org identifier (UUID, slug, or name) to its UUID string."""
    # Try UUID
    try:
        _uuid.UUID(value)
        if Organization.objects.filter(id=value, is_active=True).exists():
            return value
    except (ValueError, AttributeError):
        pass

    # Try slug
    org = Organization.objects.filter(slug=value, is_active=True).first()
    if org:
        return str(org.id)

    # Try name (case-insensitive)
    org = Organization.objects.filter(name__iexact=value, is_active=True).first()
    if org:
        return str(org.id)

    # Auto-detect single org
    orgs = Organization.objects.filter(is_active=True)
    if orgs.count() == 1:
        return str(orgs.first().id)

    raise ValueError(f"Organization not found: {value}")
