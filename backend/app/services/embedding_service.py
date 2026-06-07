"""
app/services/embedding_service.py
====================================
LaBSE sentence embedding service for semantic similarity computation (Stage 8).

## Model

Language-agnostic BERT Sentence Embeddings (LaBSE)
    - HuggingFace: `sentence-transformers/LaBSE`
    - Embedding dimension: 768
    - Languages: 109 languages including Bangla (bn)
    - Normalised embeddings → cosine similarity = dot product

LaBSE is the optimal choice for Bangla fact-checking because:
1. Trained on multilingual parallel corpora including bn-en pairs.
2. Handles Bangla script natively without transliteration.
3. Produces semantically meaningful embeddings for mixed bn/en text
   (common in Bangladeshi news articles).

## Architecture

The model is loaded ONCE at application startup (lifespan event) and shared
across all requests via a singleton. Loading takes ~3–5 seconds and ~1.5 GB RAM.

## Caching

Embeddings are cached in Redis with key `bgf:emb:{text_hash}` and a 24-hour TTL.
This avoids re-encoding the same article text across multiple verification
requests for the same article.

## Async wrapping

`sentence-transformers` is synchronous. All encoding calls are dispatched to
a `ThreadPoolExecutor` to keep the FastAPI event loop responsive.
"""

from __future__ import annotations

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

import numpy as np
import structlog
from sentence_transformers import SentenceTransformer

from app.core.config import get_settings
from app.services.cache_service import CacheService
from app.utils.hashing import compute_text_hash
from app.utils.text_cleaner import truncate_for_nli

logger = structlog.get_logger(__name__)
_SETTINGS = get_settings()

_MODEL_NAME = "sentence-transformers/LaBSE"
_EMBEDDING_DIM = 768
_CACHE_KEY_PREFIX = "bgf:emb"
_CACHE_TTL_SECONDS = 86_400  # 24 hours

# Thread pool dedicated to CPU-bound sentence encoding
_ENCODER_POOL = ThreadPoolExecutor(
    max_workers=_SETTINGS.ml.embedding_thread_workers,
    thread_name_prefix="labse-encoder",
)


class EmbeddingService:
    """
    Singleton service that loads LaBSE and provides async sentence encoding
    with Redis-backed embedding cache.

    Usage::

        service = EmbeddingService(cache_service)
        await service.load()  # called once at startup

        similarity = await service.compute_similarity(text_a, text_b)
    """

    _model: SentenceTransformer | None = None
    _loaded: bool = False

    def __init__(self, cache_service: CacheService) -> None:
        """
        Args:
            cache_service: Redis cache abstraction for embedding storage.
        """
        self._cache = cache_service

    async def load(self) -> None:
        """
        Load the LaBSE model into memory (called once at application startup).

        This is a blocking operation (~3–5 s) and must be called from the
        FastAPI lifespan startup hook before handling any requests.
        """
        if EmbeddingService._loaded:
            return
        loop = asyncio.get_event_loop()
        logger.info("loading_labse_model", model=_MODEL_NAME)
        try:
            EmbeddingService._model = await loop.run_in_executor(
                _ENCODER_POOL,
                lambda: SentenceTransformer(_MODEL_NAME),
            )
            EmbeddingService._loaded = True
            logger.info("labse_model_loaded")
        except Exception as exc:
            logger.error("labse_model_load_failed", error=str(exc))
            raise

    async def encode(self, text: str) -> np.ndarray:
        """
        Encode a single text into a LaBSE embedding vector.

        Checks Redis cache first. On a miss, encodes in thread pool and
        writes the result back to cache (non-blocking fire-and-forget).

        Args:
            text: Input text (Bangla, English, or mixed). Will be truncated
                  to `max_chars` characters if longer.

        Returns:
            Numpy array of shape (768,) representing the sentence embedding.

        Raises:
            RuntimeError: If the model has not been loaded.
        """
        if not EmbeddingService._loaded or EmbeddingService._model is None:
            raise RuntimeError(
                "EmbeddingService.load() must be called before encoding."
            )

        # Truncate to safe NLI length for consistency with NLI stage
        truncated = truncate_for_nli(text, max_chars=_SETTINGS.ml.max_text_chars_for_embedding)
        cache_key = f"{_CACHE_KEY_PREFIX}:{compute_text_hash(truncated)}"

        # L1: Redis cache lookup
        try:
            cached_bytes = await self._cache.get_raw(cache_key)
            if cached_bytes is not None:
                return np.array(json.loads(cached_bytes), dtype=np.float32)
        except Exception:  # noqa: BLE001
            pass  # Cache failure → encode fresh

        # Encode in thread pool
        loop = asyncio.get_event_loop()
        embedding: np.ndarray = await loop.run_in_executor(
            _ENCODER_POOL,
            lambda: EmbeddingService._model.encode(  # type: ignore[union-attr]
                truncated,
                normalize_embeddings=True,
                show_progress_bar=False,
                convert_to_numpy=True,
            ),
        )

        # Write-back to Redis (fire-and-forget — do not await)
        asyncio.create_task(self._write_cache(cache_key, embedding))

        return embedding

    async def encode_batch(self, texts: list[str]) -> list[np.ndarray]:
        """
        Encode multiple texts in a single batch call (more efficient than N individual calls).

        Args:
            texts: List of input texts.

        Returns:
            List of numpy arrays, one per input text.
        """
        if not EmbeddingService._loaded or EmbeddingService._model is None:
            raise RuntimeError("EmbeddingService.load() must be called first.")

        truncated_texts = [
            truncate_for_nli(t, max_chars=_SETTINGS.ml.max_text_chars_for_embedding)
            for t in texts
        ]

        loop = asyncio.get_event_loop()
        embeddings: np.ndarray = await loop.run_in_executor(
            _ENCODER_POOL,
            lambda: EmbeddingService._model.encode(  # type: ignore[union-attr]
                truncated_texts,
                normalize_embeddings=True,
                show_progress_bar=False,
                convert_to_numpy=True,
                batch_size=_SETTINGS.ml.embedding_batch_size,
            ),
        )
        return list(embeddings)

    async def compute_similarity(self, text_a: str, text_b: str) -> float:
        """
        Compute the cosine similarity between two text passages.

        Since LaBSE embeddings are L2-normalised, cosine similarity equals
        the dot product of the two embedding vectors.

        Args:
            text_a: First text (e.g. claim headline).
            text_b: Second text (e.g. article headline or body).

        Returns:
            Cosine similarity in [0.0, 1.0].
        """
        emb_a, emb_b = await asyncio.gather(
            self.encode(text_a),
            self.encode(text_b),
        )
        # Clamp to [0, 1] — LaBSE normalised embeddings give [-1, 1] cosine
        raw = float(np.dot(emb_a, emb_b))
        return max(0.0, min(1.0, raw))

    async def _write_cache(self, key: str, embedding: np.ndarray) -> None:
        """Write an embedding to Redis cache (background task)."""
        try:
            payload = json.dumps(embedding.tolist())
            await self._cache.set_raw(key, payload, ttl=_CACHE_TTL_SECONDS)
        except Exception:  # noqa: BLE001
            pass  # Cache write failure is non-fatal
