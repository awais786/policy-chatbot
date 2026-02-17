"""
Text chunking service using LangChain's CharacterTextSplitter.

Splits extracted document text into overlapping chunks suitable for
embedding and vector search.
"""

import logging
from dataclasses import dataclass

from django.conf import settings
from langchain.text_splitter import CharacterTextSplitter

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
    Split *text* into overlapping chunks using LangChain's CharacterTextSplitter.

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

    # Initialize LangChain text splitter
    text_splitter = CharacterTextSplitter(
        separator="\n",
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
    )

    try:
        # Split the text into chunks
        chunks = text_splitter.split_text(text)

        # Convert to TextChunk objects with metadata
        result = []
        current_pos = 0

        for i, chunk_content in enumerate(chunks):
            # Find the chunk position in the original text
            start_pos = text.find(chunk_content, current_pos)
            if start_pos == -1:
                start_pos = current_pos

            end_pos = start_pos + len(chunk_content)

            result.append(TextChunk(
                content=chunk_content.strip(),
                chunk_index=i,
                start_char=start_pos,
                end_char=end_pos,
            ))

            # Update position for next search
            current_pos = max(0, end_pos - chunk_overlap)

        # Filter out empty chunks
        return [chunk for chunk in result if chunk.content.strip()]

    except Exception as e:
        logger.error(f"Failed to chunk text: {e}")
        # Fallback to simple splitting if LangChain fails
        return _simple_chunk_fallback(text, chunk_size)


def _simple_chunk_fallback(text: str, chunk_size: int) -> list[TextChunk]:
    """
    Simple fallback chunking if LangChain fails.

    Args:
        text: Text to chunk
        chunk_size: Maximum chunk size

    Returns:
        List of TextChunk objects
    """
    chunks = []
    for i in range(0, len(text), chunk_size):
        chunk_text = text[i:i + chunk_size]
        if chunk_text.strip():
            chunks.append(TextChunk(
                content=chunk_text.strip(),
                chunk_index=len(chunks),
                start_char=i,
                end_char=i + len(chunk_text)
            ))
    return chunks

