
from __future__ import annotations

import asyncio
import json
import os
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

import numpy as np
import structlog
from sentence_transformers import SentenceTransformer

from app.core.config import get_settings
from app.features.cache.cache_service import CacheService
from app.shared.utils.hashing import compute_text_hash
from app.shared.utils.text_cleaner import truncate_for_nli

logger = structlog.get_logger(__name__)
_SETTINGS = get_settings()

_MODEL_NAME = "sentence-transformers/LaBSE"
_EMBEDDING_DIM = 768
_CACHE_KEY_PREFIX = "bgf:emb"
_CACHE_TTL_SECONDS = 86_400


_ENCODER_POOL = ThreadPoolExecutor(
    max_workers=_SETTINGS.ml.embedding_thread_workers,
    thread_name_prefix="labse-encoder",
)


class EmbeddingService:

    _model: SentenceTransformer | None = None
    _loaded: bool = False

    def __init__(self, cache_service: CacheService) -> None:
        self._cache = cache_service

    async def load(self) -> None:
        if EmbeddingService._loaded:
            return
        loop = asyncio.get_event_loop()
        logger.info("loading_labse_model", model=_MODEL_NAME)

        def _load() -> SentenceTransformer:


            return SentenceTransformer(
                _MODEL_NAME,
                model_kwargs={"low_cpu_mem_usage": True},
            )

        try:
            EmbeddingService._model = await loop.run_in_executor(_ENCODER_POOL, _load)
            EmbeddingService._loaded = True
            logger.info("labse_model_loaded")
        except Exception as exc:
            logger.error("labse_model_load_failed", error=str(exc))
            raise

    async def encode(self, text: str) -> np.ndarray:
        if not EmbeddingService._loaded or EmbeddingService._model is None:
            raise RuntimeError(
                "EmbeddingService.load() must be called before encoding."
            )


        truncated = truncate_for_nli(text, max_chars=_SETTINGS.ml.max_text_chars_for_embedding)
        cache_key = f"{_CACHE_KEY_PREFIX}:{compute_text_hash(truncated)}"


        try:
            cached_bytes = await self._cache.get_raw(cache_key)
            if cached_bytes is not None:
                return np.array(json.loads(cached_bytes), dtype=np.float32)
        except Exception:
            pass


        loop = asyncio.get_event_loop()
        embedding: np.ndarray = await loop.run_in_executor(
            _ENCODER_POOL,
            lambda: EmbeddingService._model.encode(
                truncated,
                normalize_embeddings=True,
                show_progress_bar=False,
                convert_to_numpy=True,
            ),
        )


        asyncio.create_task(self._write_cache(cache_key, embedding))

        return embedding

    async def encode_batch(self, texts: list[str]) -> list[np.ndarray]:
        if not EmbeddingService._loaded or EmbeddingService._model is None:
            raise RuntimeError("EmbeddingService.load() must be called first.")

        truncated_texts = [
            truncate_for_nli(t, max_chars=_SETTINGS.ml.max_text_chars_for_embedding)
            for t in texts
        ]

        loop = asyncio.get_event_loop()
        embeddings: np.ndarray = await loop.run_in_executor(
            _ENCODER_POOL,
            lambda: EmbeddingService._model.encode(
                truncated_texts,
                normalize_embeddings=True,
                show_progress_bar=False,
                convert_to_numpy=True,
                batch_size=_SETTINGS.ml.embedding_batch_size,
            ),
        )
        return list(embeddings)

    async def compute_similarity(self, text_a: str, text_b: str) -> float:
        emb_a, emb_b = await asyncio.gather(
            self.encode(text_a),
            self.encode(text_b),
        )

        raw = float(np.dot(emb_a, emb_b))
        return max(0.0, min(1.0, raw))

    async def _write_cache(self, key: str, embedding: np.ndarray) -> None:
        try:
            payload = json.dumps(embedding.tolist())
            await self._cache.set_raw(key, payload, ttl=_CACHE_TTL_SECONDS)
        except Exception:
            pass


