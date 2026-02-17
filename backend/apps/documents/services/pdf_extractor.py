"""
PDF text extraction service.

Uses PyPDF2 to extract text content from uploaded PDF files.
Handles both local file paths and Django FieldFile objects.
"""

import io
import logging
import re
import unicodedata

from django.conf import settings
from PyPDF2 import PdfReader

logger = logging.getLogger(__name__)

# Max file size we'll attempt to read into memory (default 50 MB)
MAX_PDF_BYTES = getattr(settings, "MAX_UPLOAD_SIZE", 50 * 1024 * 1024)


class PDFExtractionError(Exception):
    """Raised when PDF text extraction fails."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_text_from_file(file_field) -> dict:
    """
    Extract text and metadata from a Django FileField / FieldFile.

    Returns:
        dict with keys:
            - text:       str  — cleaned full text
            - page_count: int  — number of pages
            - page_texts: list[str] — per-page text (useful for citations)
            - metadata:   dict — PDF metadata (author, title, etc.)
    """
    try:
        file_field.seek(0)
        content = file_field.read()
        file_field.seek(0)
    except AttributeError:
        # Storage backends that don't support seek — read fresh
        try:
            content = file_field.read()
        except Exception as exc:
            raise PDFExtractionError(f"Cannot read file: {exc}") from exc
    except Exception as exc:
        raise PDFExtractionError(f"Cannot read file: {exc}") from exc

    if len(content) > MAX_PDF_BYTES:
        mb = MAX_PDF_BYTES // (1024 * 1024)
        raise PDFExtractionError(
            f"PDF is too large ({len(content) / 1024 / 1024:.1f} MB). "
            f"Maximum allowed size is {mb} MB."
        )

    return extract_text_from_bytes(content)


def extract_text_from_bytes(pdf_bytes: bytes) -> dict:
    """
    Extract text and metadata from raw PDF bytes.

    Returns:
        dict with keys:
            - text:       str  — cleaned full text
            - page_count: int  — number of pages
            - page_texts: list[str] — per-page cleaned text
            - metadata:   dict — PDF metadata
    """
    if not pdf_bytes:
        raise PDFExtractionError("Empty PDF content.")

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
    except Exception as exc:
        raise PDFExtractionError(f"Invalid or corrupted PDF: {exc}") from exc

    if len(reader.pages) == 0:
        raise PDFExtractionError("PDF has no pages.")

    page_texts = []
    for page_num, page in enumerate(reader.pages):
        try:
            raw = page.extract_text() or ""
            page_texts.append(clean_text(raw))
        except Exception as exc:
            logger.warning("Failed to extract text from page %d: %s", page_num, exc)
            page_texts.append("")

    full_text = "\n\n".join(page_texts).strip()

    # Extract PDF metadata
    pdf_metadata = {}
    if reader.metadata:
        for key in ("title", "author", "subject", "creator"):
            value = getattr(reader.metadata, key, None)
            if value:
                pdf_metadata[key] = str(value).strip()

    return {
        "text": full_text,
        "page_count": len(reader.pages),
        "page_texts": page_texts,
        "metadata": pdf_metadata,
    }


# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------

# Control characters except \n, \r, \t
_CONTROL_CHAR_RE = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]"
)

# Three or more consecutive newlines → two newlines (keep paragraph breaks)
_EXCESS_NEWLINES_RE = re.compile(r"\n{3,}")

# Two or more consecutive spaces/tabs on a single line
_EXCESS_SPACES_RE = re.compile(r"[^\S\n]{2,}")


def clean_text(raw: str) -> str:
    """
    Normalize text extracted from a PDF page.

    - Strips null bytes and control characters
    - Normalizes Unicode (NFC form)
    - Collapses excessive whitespace while preserving paragraph breaks
    - Strips leading/trailing whitespace per line
    """
    if not raw:
        return ""

    # Unicode normalize (handles ligatures like ﬁ → fi)
    text = unicodedata.normalize("NFC", raw)

    # Remove control characters (keep newlines, tabs)
    text = _CONTROL_CHAR_RE.sub("", text)

    # Replace non-breaking spaces and other Unicode spaces with normal space
    text = text.replace("\u00a0", " ").replace("\u200b", "")

    # Collapse excessive spaces on each line
    text = _EXCESS_SPACES_RE.sub(" ", text)

    # Collapse excessive newlines (keep max 2 for paragraph breaks)
    text = _EXCESS_NEWLINES_RE.sub("\n\n", text)

    # Strip each line individually
    lines = [line.strip() for line in text.splitlines()]
    text = "\n".join(lines)

    return text.strip()
