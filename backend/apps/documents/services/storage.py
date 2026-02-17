"""
Document storage service — S3 integration.

Handles uploading, downloading, and deleting PDF files in the
configured AWS S3 bucket with organization-scoped prefixes.
"""

import hashlib
from datetime import date


def document_upload_path(instance, filename):
    """Generate upload path: {org_slug}/{YYYY-MM-DD}/{filename}."""
    org_slug = instance.organization.slug
    today = date.today().isoformat()
    return f"{org_slug}/{today}/{filename}"


def compute_file_hash(file):
    """Compute SHA-256 hash of an uploaded file, reading in chunks.

    Resets the file pointer to the beginning after hashing so the file
    can be read again for storage.
    """
    hasher = hashlib.sha256()
    for chunk in file.chunks():
        hasher.update(chunk)
    file.seek(0)
    return hasher.hexdigest()
