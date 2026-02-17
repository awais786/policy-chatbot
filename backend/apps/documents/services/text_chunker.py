"""
Text chunking service.

Splits extracted document text into overlapping chunks suitable for
embedding and vector search. Uses a recursive character-based splitter
that respects paragraph/sentence boundaries.
"""

import logging
import re
from dataclasses import dataclass

from django.conf import settings

logger = logging.getLogger(__name__)

# Separators ordered from strongest to weakest boundary
SEPARATORS = [
    "\n\n",   # paragraph breaks
    "\n",     # line breaks
    ". ",     # sentence breaks
    "? ",
    "! ",
    "; ",
    ", ",
    " ",      # word breaks
    "",        # character-level fallback
]


@dataclass
class TextChunk:
    """A single text chunk with positional metadata."""
    content: str
    chunk_index: int
    start_char: int
    end_char: int


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[TextChunk]:
    """
    Split *text* into overlapping chunks using recursive character splitting.

    Uses paragraph → sentence → word boundaries to find clean break points.

    Args:
        text: The full document text to split.
        chunk_size: Max characters per chunk (default: settings.CHUNK_SIZE).
        chunk_overlap: Overlap characters between chunks (default: settings.CHUNK_OVERLAP).

    Returns:
        List of TextChunk dataclass instances.
    """
    chunk_size = chunk_size or getattr(settings, "CHUNK_SIZE", 1000)
    chunk_overlap = chunk_overlap or getattr(settings, "CHUNK_OVERLAP", 200)

    if not text or not text.strip():
        return []

    raw_chunks = _recursive_split(text, chunk_size, SEPARATORS)

    # Merge very small chunks with their neighbors
    merged = _merge_small_chunks(raw_chunks, chunk_size)

    # Apply overlap by including trailing text from previous chunk
    result = []
    for i, chunk_content in enumerate(merged):
        start_char = text.find(chunk_content)
        if start_char == -1:
            start_char = 0

        result.append(TextChunk(
            content=chunk_content.strip(),
            chunk_index=i,
            start_char=start_char,
            end_char=start_char + len(chunk_content),
        ))

    # Apply overlap: prepend tail of previous chunk to current
    overlapped = []
    for i, chunk in enumerate(result):
        if i == 0 or chunk_overlap <= 0:
            overlapped.append(chunk)
            continue

        prev_content = result[i - 1].content
        overlap_text = prev_content[-chunk_overlap:] if len(prev_content) > chunk_overlap else prev_content

        # Find a clean word boundary in the overlap
        space_idx = overlap_text.find(" ")
        if space_idx != -1:
            overlap_text = overlap_text[space_idx + 1:]

        combined = f"{overlap_text} {chunk.content}".strip()
        overlapped.append(TextChunk(
            content=combined,
            chunk_index=chunk.chunk_index,
            start_char=chunk.start_char,
            end_char=chunk.end_char,
        ))

    # Filter out empty chunks
    return [c for c in overlapped if c.content]


def _recursive_split(text: str, chunk_size: int, separators: list[str]) -> list[str]:
    """Recursively split text using progressively weaker separators."""
    if len(text) <= chunk_size:
        return [text]

    # Find the best separator that actually exists in the text
    separator = ""
    for sep in separators:
        if sep in text:
            separator = sep
            break

    if not separator:
        # No separator found — hard split at chunk_size
        return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

    parts = text.split(separator)
    chunks = []
    current = ""

    for part in parts:
        candidate = f"{current}{separator}{part}" if current else part

        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                chunks.append(current)
            # If a single part exceeds chunk_size, split it with weaker separators
            if len(part) > chunk_size:
                remaining_seps = separators[separators.index(separator) + 1:]
                chunks.extend(_recursive_split(part, chunk_size, remaining_seps))
                current = ""
            else:
                current = part

    if current:
        chunks.append(current)

    return chunks


def _merge_small_chunks(chunks: list[str], chunk_size: int, min_size: int = 50) -> list[str]:
    """Merge chunks smaller than *min_size* with the next chunk."""
    if not chunks:
        return chunks

    merged = []
    buffer = ""

    for chunk in chunks:
        if buffer:
            candidate = f"{buffer} {chunk}"
            if len(candidate) <= chunk_size:
                buffer = candidate
                continue
            else:
                merged.append(buffer)
                buffer = ""

        if len(chunk) < min_size:
            buffer = chunk
        else:
            merged.append(chunk)

    if buffer:
        if merged:
            # Attach to last chunk if it fits
            if len(merged[-1]) + len(buffer) + 1 <= chunk_size:
                merged[-1] = f"{merged[-1]} {buffer}"
            else:
                merged.append(buffer)
        else:
            merged.append(buffer)

    return merged
