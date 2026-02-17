"""
Embedding generation service.

Generates vector embeddings for text chunks using OpenAI's embedding API,
then stores them on DocumentChunk rows in pgvector.
"""

import logging
from typing import Sequence

from django.conf import settings

import openai

logger = logging.getLogger(__name__)

# OpenAI recommends batches of up to 2048 inputs
MAX_BATCH_SIZE = 2048


class EmbeddingError(Exception):
    """Raised when embedding generation fails."""


def get_openai_client() -> openai.OpenAI:
    """Return a configured OpenAI client."""
    api_key = getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        raise EmbeddingError(
            "OPENAI_API_KEY is not configured. "
            "Set the OPENAI_API_KEY environment variable."
        )
    return openai.OpenAI(api_key=api_key)


def generate_embeddings(
    texts: Sequence[str],
    model: str | None = None,
    dimensions: int | None = None,
) -> list[list[float]]:
    """
    Generate embeddings for a list of texts using OpenAI.

    Args:
        texts: Sequence of text strings to embed.
        model: Embedding model name (default: settings.EMBEDDING_MODEL).
        dimensions: Vector dimensions (default: settings.EMBEDDING_DIMENSIONS).

    Returns:
        List of embedding vectors (same order as input texts).

    Raises:
        EmbeddingError: If the API call fails.
    """
    model = model or getattr(settings, "EMBEDDING_MODEL", "text-embedding-3-small")
    dimensions = dimensions or getattr(settings, "EMBEDDING_DIMENSIONS", 1536)

    if not texts:
        return []

    client = get_openai_client()
    all_embeddings: list[list[float]] = [[] for _ in texts]

    # Process in batches
    for batch_start in range(0, len(texts), MAX_BATCH_SIZE):
        batch = list(texts[batch_start: batch_start + MAX_BATCH_SIZE])

        # Replace empty strings with a placeholder to avoid API errors
        cleaned_batch = [t if t.strip() else "empty" for t in batch]

        try:
            response = client.embeddings.create(
                input=cleaned_batch,
                model=model,
                dimensions=dimensions,
            )

            for item in response.data:
                global_idx = batch_start + item.index
                all_embeddings[global_idx] = item.embedding

        except openai.APIError as exc:
            raise EmbeddingError(f"OpenAI API error: {exc}") from exc
        except Exception as exc:
            raise EmbeddingError(f"Embedding generation failed: {exc}") from exc

    return all_embeddings


def generate_single_embedding(
    text: str,
    model: str | None = None,
    dimensions: int | None = None,
) -> list[float]:
    """
    Convenience wrapper to embed a single text string.

    Returns:
        A single embedding vector.
    """
    results = generate_embeddings([text], model=model, dimensions=dimensions)
    return results[0]
