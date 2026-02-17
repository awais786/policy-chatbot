"""
Document storage service — S3 integration.

Handles uploading, downloading, and deleting PDF files in the
configured AWS S3 bucket with organization-scoped prefixes.
"""

import hashlib
import uuid
from datetime import date
from django.utils.text import get_valid_filename


def document_upload_path(instance, filename):
    """Generate a safe upload path:

    documents/{org_slug}/{YYYY-MM-DD}/{uuid_hex}_{safe_filename}

    - Uses a sanitized filename to avoid problematic characters.
    - Prefixes with a UUID to avoid collisions when multiple uploads use the same name.
    - Falls back to 'org' if the instance or organization slug is missing.
    """
    org_slug = None
    try:
        org_slug = getattr(instance, 'organization', None) and getattr(instance.organization, 'slug', None)
    except Exception:
        org_slug = None
    if not org_slug:
        org_slug = 'org'

    today = date.today().isoformat()
    safe_name = get_valid_filename(filename)
    # Keep filenames reasonably sized
    if len(safe_name) > 120:
        # keep the extension if present
        parts = safe_name.rsplit('.', 1)
        ext = f".{parts[1]}" if len(parts) == 2 else ''
        base = parts[0][:120 - len(ext)]
        safe_name = base + ext

    uid = uuid.uuid4().hex
    return f"documents/{org_slug}/{today}/{uid}_{safe_name}"


def compute_file_hash(file):
    """Compute SHA-256 hash of an uploaded file, reading in chunks.

    Resets the file pointer to the beginning after hashing so the file
    can be read again for storage.
    """
    hasher = hashlib.sha256()
    for chunk in file.chunks():
        hasher.update(chunk)
    try:
        file.seek(0)
    except Exception:
        # Not all file-like objects support seek; ignore if not supported
        pass
    return hasher.hexdigest()
