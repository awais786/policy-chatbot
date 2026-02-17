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

        try:
            self.client = openai.OpenAI(api_key=api_key)
        except Exception as e:
            raise EmbeddingError(f"Failed to initialize OpenAI client: {e}") from e

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

        # Ensure base_url doesn't end with slash to avoid issues
        if base_url.endswith('/'):
            base_url = base_url.rstrip('/')

        try:
            self.client = openai.OpenAI(
                base_url=f"{base_url}/v1",
                api_key="ollama"  # Ollama ignores the key but the client requires one
            )
        except Exception as e:
            raise EmbeddingError(
                f"Failed to initialize Ollama client. "
                f"Make sure Ollama is running at {base_url}. "
                f"Error: {e}"
            ) from e

        self.model = getattr(settings, "OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")

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
# Hugging Face provider (local, no server required)
# ---------------------------------------------------------------------------

class HuggingFaceEmbeddingProvider(BaseEmbeddingProvider):
    """Generate embeddings using Hugging Face sentence-transformers locally.

    This provider runs completely offline and doesn't require any external
    services like Ollama or OpenAI. It uses the sentence-transformers library
    to run models locally on your machine.
    """

    def __init__(self):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise EmbeddingError(
                "sentence-transformers library is required for Hugging Face embeddings. "
                "Install it with: pip install sentence-transformers"
            )

        self.model_name = getattr(
            settings, "HUGGINGFACE_EMBEDDING_MODEL",
            getattr(settings, "WAGTAIL_RAG_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        )

        try:
            logger.info(f"Loading Hugging Face model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            logger.info(f"Successfully loaded Hugging Face model: {self.model_name}")
        except Exception as e:
            raise EmbeddingError(f"Failed to load Hugging Face model {self.model_name}: {e}")

    def provider_name(self) -> str:
        return f"huggingface ({self.model_name})"

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        try:
            # Generate embeddings using sentence-transformers
            embeddings = self.model.encode(
                texts,
                convert_to_tensor=False,  # Return as numpy arrays
                show_progress_bar=len(texts) > 10,  # Show progress for large batches
                batch_size=32  # Process in batches for memory efficiency
            )

            # Convert numpy arrays to Python lists
            return [embedding.tolist() for embedding in embeddings]

        except Exception as e:
            raise EmbeddingError(f"Failed to generate embeddings with {self.model_name}: {e}")


# ---------------------------------------------------------------------------
# Provider registry & factory
# ---------------------------------------------------------------------------

PROVIDERS = {
    "openai": OpenAIEmbeddingProvider,
    "ollama": OllamaEmbeddingProvider,
    "huggingface": HuggingFaceEmbeddingProvider,
}


def get_embedding_provider() -> BaseEmbeddingProvider:
    """
    Return the embedding provider configured in settings.EMBEDDING_PROVIDER.

    Defaults to "huggingface" if not set (no external dependencies required).
    """
    name = getattr(settings, "EMBEDDING_PROVIDER", "huggingface")
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


def test_embedding_service() -> dict:
    """
    Test the embedding service to ensure it's working correctly.

    Returns:
        Dictionary with test results and configuration info.
    """
    result = {
        "provider": getattr(settings, "EMBEDDING_PROVIDER", "openai"),
        "success": False,
        "error": None,
        "dimensions": None,
        "test_text": "This is a test for embedding generation."
    }

    try:
        provider = get_embedding_provider()
        result["provider_name"] = provider.provider_name()

        # Test with a simple text
        embedding = generate_single_embedding(result["test_text"])

        if isinstance(embedding, list) and len(embedding) > 0:
            result["success"] = True
            result["dimensions"] = len(embedding)
            logger.info(f"Embedding test successful with {result['provider_name']}, dimensions: {len(embedding)}")
        else:
            result["error"] = "Invalid embedding format returned"

    except EmbeddingError as e:
        result["error"] = str(e)
        logger.error(f"Embedding test failed: {e}")
    except Exception as e:
        result["error"] = f"Unexpected error: {e}"
        logger.error(f"Embedding test failed with unexpected error: {e}")

    return result
