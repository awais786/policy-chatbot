"""
Embedding generation service with pluggable providers.

Supports backends controlled by settings.EMBEDDING_PROVIDER:
    - "ollama"      — local Ollama server (free, default for development)
    - "openai"      — OpenAI embedding API (production)
    - "huggingface" — local sentence-transformers (no server needed)

Both Ollama and OpenAI providers use the ``openai`` Python library since
Ollama exposes an OpenAI-compatible API at /v1/.
"""

import abc
import logging
import threading
from typing import Sequence

from django.conf import settings

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
        import openai

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
        return f"openai ({self.model}, dim={self.dimensions})"

    def embed(self, texts: list[str]) -> list[list[float]]:
        import openai

        all_embeddings: list[list[float] | None] = [None] * len(texts)

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
            except openai.APIConnectionError as exc:
                raise EmbeddingError(
                    f"Cannot connect to OpenAI API: {exc}"
                ) from exc
            except openai.RateLimitError as exc:
                raise EmbeddingError(
                    f"OpenAI rate limit exceeded: {exc}"
                ) from exc
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
        import openai

        base_url = getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")
        base_url = base_url.rstrip("/")

        self.client = openai.OpenAI(
            base_url=f"{base_url}/v1",
            api_key="ollama",  # Ollama ignores the key but the client requires one
        )
        self.model = getattr(settings, "OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
        self._base_url = base_url

    def provider_name(self) -> str:
        return f"ollama ({self.model} @ {self._base_url})"

    def embed(self, texts: list[str]) -> list[list[float]]:
        import openai

        all_embeddings: list[list[float] | None] = [None] * len(texts)

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
                    f"Cannot connect to Ollama at {self._base_url}. "
                    f"Is Ollama running? ('ollama serve'). Error: {exc}"
                ) from exc
            except openai.APIError as exc:
                raise EmbeddingError(f"Ollama API error: {exc}") from exc

        return all_embeddings


# ---------------------------------------------------------------------------
# Hugging Face provider (local, no server required)
# ---------------------------------------------------------------------------

class HuggingFaceEmbeddingProvider(BaseEmbeddingProvider):
    """Generate embeddings using sentence-transformers locally.

    Runs completely offline. The model is loaded once on first use
    and reused for subsequent calls (provider is cached at module level).
    """

    def __init__(self):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise EmbeddingError(
                "sentence-transformers is required for the 'huggingface' provider. "
                "Install with: pip install sentence-transformers"
            )

        self.model_name = (
            getattr(settings, "HUGGINGFACE_EMBEDDING_MODEL", "")
            or getattr(settings, "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        )

        try:
            logger.info("Loading Hugging Face model: %s", self.model_name)
            self._model = SentenceTransformer(self.model_name)
        except Exception as exc:
            raise EmbeddingError(
                f"Failed to load model '{self.model_name}': {exc}"
            ) from exc

    def provider_name(self) -> str:
        return f"huggingface ({self.model_name})"

    def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            vectors = self._model.encode(
                texts,
                convert_to_tensor=False,
                show_progress_bar=len(texts) > 50,
                batch_size=32,
            )
            return [v.tolist() for v in vectors]
        except Exception as exc:
            raise EmbeddingError(
                f"HuggingFace embedding failed: {exc}"
            ) from exc


# ---------------------------------------------------------------------------
# Provider registry, caching & factory
# ---------------------------------------------------------------------------

PROVIDERS = {
    "openai": OpenAIEmbeddingProvider,
    "ollama": OllamaEmbeddingProvider,
    "huggingface": HuggingFaceEmbeddingProvider,
}

_provider_cache: BaseEmbeddingProvider | None = None
_provider_cache_key: str | None = None
_cache_lock = threading.Lock()


def get_embedding_provider() -> BaseEmbeddingProvider:
    """
    Return the configured embedding provider (cached singleton).

    The provider is re-created only when ``EMBEDDING_PROVIDER`` changes,
    avoiding expensive re-initialization (HTTP clients, HF model loads).
    """
    global _provider_cache, _provider_cache_key

    name = getattr(settings, "EMBEDDING_PROVIDER", "ollama")

    # Fast path — return cached provider
    if _provider_cache is not None and _provider_cache_key == name:
        return _provider_cache

    with _cache_lock:
        # Double-check under lock
        if _provider_cache is not None and _provider_cache_key == name:
            return _provider_cache

        provider_cls = PROVIDERS.get(name)
        if provider_cls is None:
            raise EmbeddingError(
                f"Unknown EMBEDDING_PROVIDER '{name}'. "
                f"Choose from: {', '.join(PROVIDERS)}"
            )

        _provider_cache = provider_cls()
        _provider_cache_key = name
        logger.info("Initialized embedding provider: %s", _provider_cache.provider_name())
        return _provider_cache


def reset_provider_cache():
    """Clear the cached provider. Useful for testing or after settings change."""
    global _provider_cache, _provider_cache_key
    with _cache_lock:
        _provider_cache = None
        _provider_cache_key = None


# ---------------------------------------------------------------------------
# Public API (used by the Celery task)
# ---------------------------------------------------------------------------

def generate_embeddings(texts: Sequence[str]) -> list[list[float]]:
    """
    Generate embeddings for a list of texts using the configured provider.

    Returns:
        List of embedding vectors (same order as input texts).
        Individual items may be None if that specific text failed.

    Raises:
        EmbeddingError: If the provider fails entirely.
    """
    if not texts:
        return []

    provider = get_embedding_provider()
    logger.info(
        "Generating embeddings with %s for %d texts",
        provider.provider_name(), len(texts),
    )

    try:
        embeddings = provider.embed(list(texts))
    except EmbeddingError:
        raise
    except Exception as exc:
        raise EmbeddingError(f"Embedding generation failed: {exc}") from exc

    # Validate dimensions if configured
    expected_dim = getattr(settings, "EMBEDDING_DIMENSIONS", None)
    if expected_dim and embeddings:
        for i, vec in enumerate(embeddings):
            if vec is not None and len(vec) != expected_dim:
                logger.warning(
                    "Embedding %d has dimension %d, expected %d. "
                    "Check EMBEDDING_DIMENSIONS matches your model.",
                    i, len(vec), expected_dim,
                )
                break  # Log once, not for every vector

    return embeddings


def generate_single_embedding(text: str) -> list[float]:
    """Embed a single text string."""
    results = generate_embeddings([text])
    if not results or results[0] is None:
        raise EmbeddingError("Failed to generate embedding for the given text.")
    return results[0]
