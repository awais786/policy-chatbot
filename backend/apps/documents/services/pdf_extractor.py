"""
Robust PDF text extraction with automatic quality-based strategy selection.

Extraction cascade (best result wins):
  1. pdfplumber  — structured text + table extraction
  2. PyMuPDF     — fast, handles complex / multi-column layouts
  3. PyPDF2      — lightweight last-resort fallback

Each method is scored for quality; the pipeline short-circuits once a
result exceeds the quality threshold.
"""

import io
import logging
import re
from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency imports
# ---------------------------------------------------------------------------

try:
    import pdfplumber

    PDFPLUMBER_AVAILABLE = True
except ImportError:
    pdfplumber = None
    PDFPLUMBER_AVAILABLE = False

try:
    from PyPDF2 import PdfReader

    PYPDF2_AVAILABLE = True
except ImportError:
    PdfReader = None
    PYPDF2_AVAILABLE = False

try:
    import fitz  # PyMuPDF

    PYMUPDF_AVAILABLE = True
except ImportError:
    fitz = None
    PYMUPDF_AVAILABLE = False


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class ExtractionMethod(str, Enum):
    PDFPLUMBER = "pdfplumber"
    PYMUPDF = "pymupdf"
    PYPDF2 = "pypdf2"


class PDFExtractionError(Exception):
    """Raised when PDF text extraction fails."""


@dataclass
class ExtractionResult:
    text: str
    page_count: int
    page_texts: List[str]
    metadata: Dict[str, Any]
    quality_score: float = 0.0
    method: ExtractionMethod = ExtractionMethod.PDFPLUMBER


# ---------------------------------------------------------------------------
# Quality assessment
# ---------------------------------------------------------------------------

_QUALITY_THRESHOLD = 0.40


def _assess_text_quality(text: str, page_count: int = 1) -> float:
    """
    Score extracted text from 0.0 (garbage / empty) to 1.0 (clean text).

    Factors: character density per page, printable-character ratio,
    proportion of word-like tokens, average token length.
    """
    if not text or not text.strip():
        return 0.0

    chars = len(text)
    chars_per_page = chars / max(page_count, 1)

    if chars_per_page < 50:
        return 0.1

    printable = sum(1 for c in text if c.isprintable() or c in "\n\r\t")
    printable_ratio = printable / max(chars, 1)

    tokens = text.split()
    if not tokens:
        return 0.1

    alpha_tokens = sum(
        1 for t in tokens if any(c.isalpha() for c in t) and len(t) >= 2
    )
    alpha_ratio = alpha_tokens / len(tokens)

    avg_len = sum(len(t) for t in tokens) / len(tokens)
    len_score = 1.0 if 3 <= avg_len <= 12 else max(0.0, 1 - abs(avg_len - 7) / 15)

    density_score = min(1.0, chars_per_page / 300)

    score = (
        printable_ratio * 0.25
        + alpha_ratio * 0.30
        + len_score * 0.20
        + density_score * 0.25
    )
    return round(min(1.0, max(0.0, score)), 3)


# ---------------------------------------------------------------------------
# Text cleanup helpers
# ---------------------------------------------------------------------------


def preprocess_extracted_text(text: str) -> str:
    """Normalize raw PDF text (whitespace, quotes, bullets, null bytes)."""
    if not text:
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\u201c|\u201d", '"', text)
    text = re.sub(r"\u2018|\u2019|\u0060", "'", text)
    text = re.sub(r"\u2013|\u2014", "-", text)
    text = re.sub(r"\uf0b7|\u2022|\u25cf", "- ", text)
    text = re.sub(r"\x00", "", text)
    return text.strip()


def _remove_headers_footers(
    page_texts: List[str], threshold: float = 0.6
) -> List[str]:
    """
    Strip repeating header / footer lines that appear on >= *threshold*
    fraction of pages.  Page numbers are normalised so "Page 1" and "Page 7"
    collapse to the same pattern.
    """
    if len(page_texts) < 4:
        return page_texts

    first_lines_counter: Counter = Counter()
    last_lines_counter: Counter = Counter()

    for pt in page_texts:
        lines = [ln.strip() for ln in pt.split("\n") if ln.strip()]
        for line in lines[:3]:
            normalised = re.sub(r"\d+", "#", line.strip().lower())
            if len(normalised) > 3:
                first_lines_counter[normalised] += 1
        for line in lines[-3:]:
            normalised = re.sub(r"\d+", "#", line.strip().lower())
            if len(normalised) > 3:
                last_lines_counter[normalised] += 1

    n_pages = len(page_texts)
    repeating = {
        pat
        for counter in (first_lines_counter, last_lines_counter)
        for pat, count in counter.items()
        if count / n_pages >= threshold
    }

    cleaned = []
    for pt in page_texts:
        lines = pt.split("\n")
        filtered = [
            ln
            for ln in lines
            if re.sub(r"\d+", "#", ln.strip().lower()) not in repeating
        ]
        cleaned.append("\n".join(filtered))
    return cleaned


def _format_table_as_text(table) -> str:
    """Convert a pdfplumber table (list of rows) to pipe-delimited text."""
    rows = []
    for row in table or []:
        cells = [str(cell).strip() if cell is not None else "" for cell in row]
        if any(cells):
            rows.append(" | ".join(cells))
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# Extraction backends
# ---------------------------------------------------------------------------


def _extract_with_pdfplumber(pdf_bytes: bytes) -> ExtractionResult:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        page_texts: List[str] = []
        table_segments: List[str] = []
        tables_found = 0

        for page in pdf.pages:
            raw = page.extract_text() or ""
            cleaned = preprocess_extracted_text(raw)
            page_texts.append(cleaned)

            for table in page.extract_tables() or []:
                table_text = _format_table_as_text(table)
                if table_text:
                    tables_found += 1
                    table_segments.append(f"[TABLE]\n{table_text}\n[/TABLE]")

        page_texts = _remove_headers_footers(page_texts)
        all_segments = [pt for pt in page_texts if pt.strip()] + table_segments
        text = "\n\n".join(all_segments).strip()
        meta = pdf.metadata or {}

        return ExtractionResult(
            text=text,
            page_count=len(pdf.pages),
            page_texts=page_texts,
            metadata={
                "extraction_method": ExtractionMethod.PDFPLUMBER.value,
                "tables_found": tables_found,
                "title": str(meta.get("Title", "") or ""),
                "author": str(meta.get("Author", "") or ""),
                "subject": str(meta.get("Subject", "") or ""),
                "creator": str(meta.get("Creator", "") or ""),
            },
            quality_score=_assess_text_quality(text, len(pdf.pages)),
            method=ExtractionMethod.PDFPLUMBER,
        )


def _extract_with_pymupdf(pdf_bytes: bytes) -> ExtractionResult:
    """PyMuPDF dict-mode extraction preserves reading order across columns."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        page_texts: List[str] = []
        for page in doc:
            blocks = page.get_text("dict", sort=True).get("blocks", [])
            page_lines: List[str] = []
            for block in blocks:
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    span_text = "".join(
                        span.get("text", "") for span in line.get("spans", [])
                    )
                    if span_text.strip():
                        page_lines.append(span_text.strip())
            page_texts.append(preprocess_extracted_text("\n".join(page_lines)))

        page_texts = _remove_headers_footers(page_texts)
        text = "\n\n".join(pt for pt in page_texts if pt.strip()).strip()
        meta = doc.metadata or {}

        return ExtractionResult(
            text=text,
            page_count=len(doc),
            page_texts=page_texts,
            metadata={
                "extraction_method": ExtractionMethod.PYMUPDF.value,
                "title": meta.get("title", ""),
                "author": meta.get("author", ""),
                "subject": meta.get("subject", ""),
                "creator": meta.get("creator", ""),
            },
            quality_score=_assess_text_quality(text, len(doc)),
            method=ExtractionMethod.PYMUPDF,
        )
    finally:
        doc.close()


def _extract_with_pypdf2(pdf_bytes: bytes) -> ExtractionResult:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    page_texts = [
        preprocess_extracted_text(p.extract_text() or "") for p in reader.pages
    ]
    page_texts = _remove_headers_footers(page_texts)
    text = "\n\n".join(pt for pt in page_texts if pt.strip()).strip()
    meta = reader.metadata or {}

    return ExtractionResult(
        text=text,
        page_count=len(reader.pages),
        page_texts=page_texts,
        metadata={
            "extraction_method": ExtractionMethod.PYPDF2.value,
            "title": str(meta.get("/Title", "") or ""),
            "author": str(meta.get("/Author", "") or ""),
            "subject": str(meta.get("/Subject", "") or ""),
        },
        quality_score=_assess_text_quality(text, len(reader.pages)),
        method=ExtractionMethod.PYPDF2,
    )


# ---------------------------------------------------------------------------
# Main entry point  (same interface as the previous version)
# ---------------------------------------------------------------------------


def extract_text_from_file(file_field) -> Dict[str, Any]:
    """
    Extract text and metadata from a Django FileField / FieldFile.

    Tries every available backend in quality order, short-circuiting as
    soon as the quality score exceeds the threshold.

    Returns:
        {
            "text": str,
            "page_count": int,
            "page_texts": list[str],
            "metadata": dict,
        }
    """
    if not file_field:
        raise PDFExtractionError("No file provided for text extraction")

    available = [
        name
        for name, ok in [
            ("pdfplumber", PDFPLUMBER_AVAILABLE),
            ("PyMuPDF", PYMUPDF_AVAILABLE),
            ("PyPDF2", PYPDF2_AVAILABLE),
        ]
        if ok
    ]
    if not available:
        raise PDFExtractionError(
            "No PDF library installed. "
            "Install at least one: pip install pdfplumber PyMuPDF PyPDF2"
        )

    try:
        file_field.seek(0)
        pdf_bytes = file_field.read()
        file_field.seek(0)
    except Exception as exc:
        raise PDFExtractionError(f"Could not read file bytes: {exc}") from exc

    if not pdf_bytes:
        raise PDFExtractionError("Uploaded file is empty")

    best: Optional[ExtractionResult] = None
    attempts: List[str] = []

    strategies = _build_strategy_list()

    for name, extractor in strategies:
        try:
            result = extractor(pdf_bytes)
            attempts.append(f"{name}(score={result.quality_score})")
            if best is None or result.quality_score > best.quality_score:
                best = result
            if best.quality_score >= _QUALITY_THRESHOLD:
                logger.info(
                    "PDF extraction succeeded with %s (score %.2f)",
                    name,
                    best.quality_score,
                )
                return _to_dict(best, attempts)
        except Exception as exc:
            attempts.append(f"{name}(failed: {exc})")
            logger.warning("Extraction method %s failed: %s", name, exc)

    if best is None or not best.text.strip():
        raise PDFExtractionError(
            f"All extraction methods failed or returned empty text. "
            f"Attempts: {attempts}"
        )

    logger.info(
        "PDF extraction best result from %s (score %.2f, below threshold %.2f)",
        best.method.value,
        best.quality_score,
        _QUALITY_THRESHOLD,
    )
    return _to_dict(best, attempts)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_strategy_list():
    """Return an ordered list of (name, callable) strategies to attempt."""
    strategies = []
    if PDFPLUMBER_AVAILABLE:
        strategies.append(("pdfplumber", _extract_with_pdfplumber))
    if PYMUPDF_AVAILABLE:
        strategies.append(("pymupdf", _extract_with_pymupdf))
    if PYPDF2_AVAILABLE:
        strategies.append(("pypdf2", _extract_with_pypdf2))
    return strategies


def _to_dict(result: ExtractionResult, attempts: List[str]) -> Dict[str, Any]:
    """Convert to the dict shape expected by the rest of the pipeline."""
    result.metadata["quality_score"] = result.quality_score
    result.metadata["extraction_attempts"] = attempts
    return {
        "text": result.text,
        "page_count": result.page_count,
        "page_texts": result.page_texts,
        "metadata": result.metadata,
    }


# ---------------------------------------------------------------------------
# Title extraction helper
# ---------------------------------------------------------------------------

_JUNK_WORDS = frozenset({
    "untitled", "document", "page", "pdf", "copy", "draft", "final",
    "version", "rev", "revision", "sample", "template", "none", "null",
    "microsoft", "word", "adobe", "acrobat",
})

# Lines that look like contact info / metadata rather than a title
_CONTACT_LINE_RE = re.compile(
    r"(?:@|\+\d|\b\d{5,}\b|linkedin|github|http|www\.|\.com|\.pk|\.io)",
    re.IGNORECASE,
)

# Lines that are clearly section headings / noise rather than a title
_NOISE_LINE_RE = re.compile(
    r"^(?:curriculum vitae|resume|cv|profile|summary|objective|"
    r"education|experience|skills|languages|references|page\s*\d+)$",
    re.IGNORECASE,
)

# City / location-only lines (e.g. "Lahore", "Lahore, Pk", "Lahore, Pakistan")
_LOCATION_LINE_RE = re.compile(
    r"^[A-Z][a-z]+(?:,\s*[A-Z][a-zA-Z]+){0,2}\.?$"
)


def _title_score(line: str) -> int:
    """
    Score a candidate title line. Higher = better title.
      +3  looks like a person name (2-4 Title Case words, no punctuation)
      +2  looks like a company / org name (contains Ltd, Inc, Pvt, Corp, etc.)
      +1  mixed case, reasonable length (8-80 chars)
       0  everything else
    """
    words = line.split()
    # Person name: 2-4 words, each starting with uppercase, no digits
    if (
        2 <= len(words) <= 4
        and all(w[0].isupper() for w in words if w)
        and not any(c.isdigit() for c in line)
        and "," not in line
    ):
        return 3
    # Company / org name
    if re.search(r"\b(?:Ltd|Pvt|Inc|Corp|LLC|Co\.|Foundation|Institute|University|Bank|Group)\b", line, re.IGNORECASE):
        return 2
    # Reasonable mixed-case line
    if 8 <= len(line) <= 80 and line != line.upper():
        return 1
    return 0


def extract_title_from_pdf_text(
    extracted_metadata: Dict[str, Any],
    extracted_text: str,
) -> Optional[str]:
    """
    Try to determine a meaningful document title from:
      1. PDF metadata fields (Title, Author)
      2. First non-trivial lines of extracted text — scored and ranked

    Returns a clean title string, or None if nothing useful is found.
    """
    # --- 1. Try PDF metadata ---
    for field in ("title", "author"):
        candidate = str(extracted_metadata.get(field) or "").strip()
        if not candidate:
            continue
        lower = candidate.lower()
        if lower in _JUNK_WORDS or len(candidate) < 3:
            continue
        if any(junk in lower for junk in _JUNK_WORDS):
            continue
        logger.debug("Title from PDF metadata (%s): %r", field, candidate)
        return candidate

    # --- 2. Scan first lines of text ---
    if not extracted_text:
        return None

    lines = [ln.strip() for ln in extracted_text.splitlines() if ln.strip()]
    candidates: List[tuple] = []  # (score, line)

    for line in lines[:30]:  # look at top of document
        if _CONTACT_LINE_RE.search(line):
            continue
        if _NOISE_LINE_RE.match(line):
            continue
        if _LOCATION_LINE_RE.match(line):
            continue
        if len(line) > 120 or len(line) < 3:
            continue
        # Skip all-uppercase lines with many words (letterhead noise)
        words = line.split()
        if len(words) > 6 and line == line.upper():
            continue
        score = _title_score(line)
        if score > 0:
            candidates.append((score, line))

    if not candidates:
        return None

    # Return the highest-scored candidate (first one if tie)
    candidates.sort(key=lambda x: -x[0])
    best = candidates[0][1]
    logger.debug("Title from text scan: %r (score=%d)", best, candidates[0][0])
    return best

