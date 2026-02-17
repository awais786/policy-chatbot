"""
Embedding generation service with pluggable providers.

Supports two backends controlled by settings.EMBEDDING_PROVIDER:
    - "ollama"  — local Ollama server (free, default for development)
    - "openai"  — OpenAI embedding API (production)

Both providers use the `openai` Python library since Ollama exposes
an OpenAI-compatible API at /v1/.
"""

import abc
import logging
from typing import Sequence

from django.conf import settings

import openai

logger = logging.getLogger(__name__)

MAX_BATCH_SIZE = 2048


class EmbeddingError(Exception):
    """Raised when embedding generation fails."""


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class BaseEmbeddingProvider(abc.ABC):
    """Interface that every embedding provider must implement."""

    @abc.abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""

    @abc.abstractmethod
    def provider_name(self) -> str:
        """Human-readable name for logging."""


# ---------------------------------------------------------------------------
# OpenAI provider
# ---------------------------------------------------------------------------

class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """Generate embeddings via the OpenAI API."""

    def __init__(self):
        api_key = getattr(settings, "OPENAI_API_KEY", "")
        if not api_key:
            raise EmbeddingError(
                "OPENAI_API_KEY is not configured. "
                "Set the OPENAI_API_KEY environment variable."
            )
        self.client = openai.OpenAI(api_key=api_key)
        self.model = getattr(settings, "EMBEDDING_MODEL", "text-embedding-3-small")
        self.dimensions = getattr(settings, "EMBEDDING_DIMENSIONS", 1536)

    def provider_name(self) -> str:
        return f"openai ({self.model})"

    def embed(self, texts: list[str]) -> list[list[float]]:
        all_embeddings: list[list[float]] = [[] for _ in texts]

        for batch_start in range(0, len(texts), MAX_BATCH_SIZE):
            batch = texts[batch_start: batch_start + MAX_BATCH_SIZE]
            cleaned = [t if t.strip() else "empty" for t in batch]

            try:
                response = self.client.embeddings.create(
                    input=cleaned,
                    model=self.model,
                    dimensions=self.dimensions,
                )
                for item in response.data:
                    all_embeddings[batch_start + item.index] = item.embedding

            except openai.APIError as exc:
                raise EmbeddingError(f"OpenAI API error: {exc}") from exc

        return all_embeddings


# ---------------------------------------------------------------------------
# Ollama provider (OpenAI-compatible endpoint)
# ---------------------------------------------------------------------------

class OllamaEmbeddingProvider(BaseEmbeddingProvider):
    """Generate embeddings via a local Ollama server.

    Ollama exposes an OpenAI-compatible API at ``/v1/``, so we reuse
    the ``openai`` Python client with a custom ``base_url``.
    """

    def __init__(self):
        base_url = getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")
        self.client = openai.OpenAI(
            base_url=f"{base_url}/v1/",
            api_key="ollama",  # Ollama ignores the key but the client requires one
        )
        self.model = getattr(
            settings, "OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"
        )

    def provider_name(self) -> str:
        return f"ollama ({self.model})"

    def embed(self, texts: list[str]) -> list[list[float]]:
        all_embeddings: list[list[float]] = [[] for _ in texts]

        for batch_start in range(0, len(texts), MAX_BATCH_SIZE):
            batch = texts[batch_start: batch_start + MAX_BATCH_SIZE]
            cleaned = [t if t.strip() else "empty" for t in batch]

            try:
                response = self.client.embeddings.create(
                    input=cleaned,
                    model=self.model,
                )
                for item in response.data:
                    all_embeddings[batch_start + item.index] = item.embedding

            except openai.APIConnectionError as exc:
                raise EmbeddingError(
                    f"Cannot connect to Ollama at {self.client.base_url}. "
                    f"Is Ollama running? Error: {exc}"
                ) from exc
            except openai.APIError as exc:
                raise EmbeddingError(f"Ollama API error: {exc}") from exc

        return all_embeddings


# ---------------------------------------------------------------------------
# Provider registry & factory
# ---------------------------------------------------------------------------

PROVIDERS = {
    "openai": OpenAIEmbeddingProvider,
    "ollama": OllamaEmbeddingProvider,
}


def get_embedding_provider() -> BaseEmbeddingProvider:
    """
    Return the embedding provider configured in settings.EMBEDDING_PROVIDER.

    Defaults to ``"ollama"`` if not set.
    """
    name = getattr(settings, "EMBEDDING_PROVIDER", "ollama")
    provider_cls = PROVIDERS.get(name)

    if provider_cls is None:
        raise EmbeddingError(
            f"Unknown EMBEDDING_PROVIDER '{name}'. "
            f"Choose from: {', '.join(PROVIDERS)}"
        )

    return provider_cls()


# ---------------------------------------------------------------------------
# Public API (used by the Celery task)
# ---------------------------------------------------------------------------

def generate_embeddings(texts: Sequence[str]) -> list[list[float]]:
    """
    Generate embeddings for a list of texts using the configured provider.

    Returns:
        List of embedding vectors (same order as input texts).
    """
    if not texts:
        return []

    provider = get_embedding_provider()
    logger.info("Generating embeddings with %s for %d texts", provider.provider_name(), len(texts))

    try:
        return provider.embed(list(texts))
    except EmbeddingError:
        raise
    except Exception as exc:
        raise EmbeddingError(f"Embedding generation failed: {exc}") from exc


def generate_single_embedding(text: str) -> list[float]:
    """Embed a single text string."""
    results = generate_embeddings([text])
    return results[0]
