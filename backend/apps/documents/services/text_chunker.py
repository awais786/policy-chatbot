"""
Text chunking service.

Splits extracted document text into overlapping chunks suitable for
embedding and vector search using LangChain's RecursiveCharacterTextSplitter.
Falls back to a built-in recursive splitter if LangChain is unavailable.
"""

import logging
from dataclasses import dataclass

from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class TextChunk:
    """A single text chunk with positional metadata."""
    content: str
    chunk_index: int
    start_char: int = 0
    end_char: int = 0


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[TextChunk]:
    """
    Split *text* into overlapping chunks.

    Uses RecursiveCharacterTextSplitter which tries paragraph → sentence →
    word boundaries (much better than CharacterTextSplitter which only
    splits on a single separator).

    Args:
        text: The full document text to split.
        chunk_size: Max characters per chunk (default: settings.CHUNK_SIZE).
        chunk_overlap: Overlap characters between chunks (default: settings.CHUNK_OVERLAP).

    Returns:
        List of TextChunk dataclass instances.
    """
    if chunk_size is None:
        chunk_size = getattr(settings, "CHUNK_SIZE", 1000)
    if chunk_overlap is None:
        chunk_overlap = getattr(settings, "CHUNK_OVERLAP", 200)

    if not text or not text.strip():
        return []

    # Ensure overlap doesn't exceed chunk size
    chunk_overlap = min(chunk_overlap, chunk_size - 1) if chunk_size > 1 else 0

    raw_chunks = _split_with_langchain(text, chunk_size, chunk_overlap)
    if raw_chunks is None:
        raw_chunks = _recursive_split_fallback(text, chunk_size, chunk_overlap)

    # Build TextChunk objects with character positions
    result = []
    search_from = 0

    for i, content in enumerate(raw_chunks):
        content = content.strip()
        if not content:
            continue

        # Track position in original text for future citation support.
        # Use a progressive search cursor to handle repeated text.
        pos = text.find(content[:80], search_from)
        start_char = pos if pos != -1 else search_from
        end_char = start_char + len(content)
        search_from = max(search_from, end_char - chunk_overlap)

        result.append(TextChunk(
            content=content,
            chunk_index=len(result),
            start_char=start_char,
            end_char=end_char,
        ))

    return result


# ---------------------------------------------------------------------------
# LangChain splitter (primary)
# ---------------------------------------------------------------------------

def _split_with_langchain(
    text: str, chunk_size: int, chunk_overlap: int
) -> list[str] | None:
    """
    Split using LangChain's RecursiveCharacterTextSplitter.

    Returns None if langchain is not installed so the caller
    can fall through to the built-in fallback.
    """
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
    except ImportError:
        logger.debug("langchain_text_splitters not installed, using built-in splitter")
        return None

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " ", ""],
    )

    try:
        return splitter.split_text(text)
    except Exception as exc:
        logger.warning("LangChain splitter failed: %s — using fallback", exc)
        return None


# ---------------------------------------------------------------------------
# Built-in recursive splitter (fallback)
# ---------------------------------------------------------------------------

_SEPARATORS = ["\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " ", ""]


def _recursive_split_fallback(
    text: str, chunk_size: int, chunk_overlap: int
) -> list[str]:
    """
    Pure-Python recursive character splitter. Tries the strongest
    separator first (paragraph break) and falls back to weaker ones.
    Produces overlapping chunks.
    """
    raw = _split_recursive(text, chunk_size, _SEPARATORS)
    if chunk_overlap <= 0 or len(raw) <= 1:
        return raw

    # Apply overlap: prepend tail of previous chunk
    overlapped = [raw[0]]
    for i in range(1, len(raw)):
        prev = raw[i - 1]
        tail = prev[-chunk_overlap:] if len(prev) > chunk_overlap else prev
        # Snap to a word boundary inside the overlap slice
        space = tail.find(" ")
        if space != -1:
            tail = tail[space + 1:]
        overlapped.append(f"{tail} {raw[i]}".strip())

    return overlapped


def _split_recursive(text: str, chunk_size: int, separators: list[str]) -> list[str]:
    """Recursively split *text* using progressively weaker separators."""
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    sep = ""
    for s in separators:
        if s in text:
            sep = s
            break

    if not sep:
        # No separator found — hard split
        return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

    parts = text.split(sep)
    remaining_seps = separators[separators.index(sep) + 1:]
    chunks: list[str] = []
    current = ""

    for part in parts:
        candidate = f"{current}{sep}{part}" if current else part

        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                chunks.append(current)
            if len(part) > chunk_size:
                chunks.extend(_split_recursive(part, chunk_size, remaining_seps))
                current = ""
            else:
                current = part

    if current.strip():
        chunks.append(current)

    return chunks
