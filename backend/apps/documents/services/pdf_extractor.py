"""
PDF text extraction service.

Uses PyPDF2 to extract text content from uploaded PDF files.
Handles both local file paths and Django FieldFile objects.
"""

import io
import logging

from PyPDF2 import PdfReader

logger = logging.getLogger(__name__)


class PDFExtractionError(Exception):
    """Raised when PDF text extraction fails."""


def extract_text_from_file(file_field) -> dict:
    """
    Extract text and metadata from a Django FileField / FieldFile.

    Returns:
        dict with keys:
            - text: str — full extracted text
            - page_count: int — number of pages
            - metadata: dict — PDF metadata (author, title, etc.)
    """
    try:
        file_field.seek(0)
        content = file_field.read()
        file_field.seek(0)
    except Exception as exc:
        raise PDFExtractionError(f"Cannot read file: {exc}") from exc

    return extract_text_from_bytes(content)


def extract_text_from_bytes(pdf_bytes: bytes) -> dict:
    """
    Extract text and metadata from raw PDF bytes.

    Returns:
        dict with keys:
            - text: str — full extracted text
            - page_count: int — number of pages
            - metadata: dict — PDF metadata
    """
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
    except Exception as exc:
        raise PDFExtractionError(f"Invalid PDF: {exc}") from exc

    pages_text = []
    for page_num, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
            pages_text.append(text)
        except Exception as exc:
            logger.warning("Failed to extract text from page %d: %s", page_num, exc)
            pages_text.append("")

    full_text = "\n\n".join(pages_text).strip()

    # Extract PDF metadata
    pdf_metadata = {}
    if reader.metadata:
        for key in ("title", "author", "subject", "creator"):
            value = getattr(reader.metadata, key, None)
            if value:
                pdf_metadata[key] = str(value)

    return {
        "text": full_text,
        "page_count": len(reader.pages),
        "metadata": pdf_metadata,
    }
