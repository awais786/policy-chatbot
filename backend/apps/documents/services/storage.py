"""
Document storage utilities.

Provides the upload path generator for FileField and a SHA-256 file hasher.
"""

import hashlib
import uuid
from datetime import date

from django.utils.text import get_valid_filename


def document_upload_path(instance, filename):
    """Return ``documents/{org_slug}/{YYYY-MM-DD}/{uuid}_{safe_name}``.

    * Sanitises the filename to strip problematic characters.
    * Prefixes a UUID to prevent collisions when the same name is reused.
    * Truncates very long filenames to 120 characters (keeping extension).
    * Falls back to ``"org"`` if the organization slug is unavailable.
    """
    org = getattr(instance, "organization", None)
    org_slug = getattr(org, "slug", None) or "org"

    today = date.today().isoformat()
    safe_name = get_valid_filename(filename)

    if len(safe_name) > 120:
        parts = safe_name.rsplit(".", 1)
        ext = f".{parts[1]}" if len(parts) == 2 else ""
        safe_name = parts[0][: 120 - len(ext)] + ext

    uid = uuid.uuid4().hex[:12]
    return f"documents/{org_slug}/{today}/{uid}_{safe_name}"


def compute_file_hash(uploaded_file):
    """Compute SHA-256 of *uploaded_file* and return the hex digest.

    Reads the file in chunks (memory-friendly for large files) and resets the
    file pointer to the beginning afterwards so Django can still store it.
    """
    hasher = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        hasher.update(chunk)
    uploaded_file.seek(0)
    return hasher.hexdigest()
