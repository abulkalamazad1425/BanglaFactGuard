"""
app/services/cache_service.py
================================
Redis cache abstraction layer used across all pipeline stages.

All Redis keys follow the `bgf:{type}:{hash}` pattern for namespacing.
TTLs are configured in AppSettings. All methods fail silently on Redis
errors — cache is a performance optimisation, not a correctness requirement.
"""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis
import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)
_SETTINGS = get_settings()

# Key prefixes
_KEY_CLAIM = "bgf:claim"
_KEY_SEARCH = "bgf:search"
_KEY_ARTICLE = "bgf:article"
_KEY_EMBEDDING = "bgf:emb"


class CacheService:
    """
    Async Redis cache service.

    All get methods return None on cache miss or error.
    All set methods are fire-and-forget safe (exceptions swallowed).
    """

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self._redis = redis_client
        self._claim_ttl = _SETTINGS.redis.ttl_claim_result
        self._search_ttl = _SETTINGS.redis.ttl_search_result
        self._article_ttl = _SETTINGS.redis.ttl_article_content

    # ------------------------------------------------------------------
    # Claim result cache (Stage 2 L1)
    # ------------------------------------------------------------------

    async def get_claim_result(self, claim_hash: str) -> bytes | None:
        """Fetch a serialised verification result from Redis."""
        try:
            return await self._redis.get(f"{_KEY_CLAIM}:{claim_hash}")
        except Exception as exc:  # noqa: BLE001
            logger.debug("cache_get_failed", key_prefix=_KEY_CLAIM, error=str(exc))
            return None

    async def set_claim_result(self, claim_hash: str, payload: str) -> None:
        """Store a serialised verification result in Redis."""
        try:
            await self._redis.set(
                f"{_KEY_CLAIM}:{claim_hash}",
                payload,
                ex=self._claim_ttl,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("cache_set_failed", key_prefix=_KEY_CLAIM, error=str(exc))

    async def invalidate_claim(self, claim_hash: str) -> None:
        """Delete a cached claim result (used on force_refresh)."""
        try:
            await self._redis.delete(f"{_KEY_CLAIM}:{claim_hash}")
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------
    # Search result cache (Stage 4)
    # ------------------------------------------------------------------

    async def get_search_result(
        self, provider: str, query_hash: str
    ) -> list[str] | None:
        """Fetch cached search result URLs for a (provider, query) pair."""
        try:
            raw = await self._redis.get(f"{_KEY_SEARCH}:{provider}:{query_hash}")
            if raw:
                return json.loads(raw)
            return None
        except Exception:  # noqa: BLE001
            return None

    async def set_search_result(
        self, provider: str, query_hash: str, urls: list[str]
    ) -> None:
        """Cache search result URLs for a (provider, query) pair."""
        try:
            await self._redis.set(
                f"{_KEY_SEARCH}:{provider}:{query_hash}",
                json.dumps(urls),
                ex=self._search_ttl,
            )
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------
    # Article content cache (Stage 6)
    # ------------------------------------------------------------------

    async def get_article(self, url_hash: str) -> dict | None:
        """Fetch cached extracted article content."""
        try:
            raw = await self._redis.get(f"{_KEY_ARTICLE}:{url_hash}")
            if raw:
                return json.loads(raw)
            return None
        except Exception:  # noqa: BLE001
            return None

    async def set_article(self, url_hash: str, content: dict) -> None:
        """Cache extracted article content."""
        try:
            await self._redis.set(
                f"{_KEY_ARTICLE}:{url_hash}",
                json.dumps(content, ensure_ascii=False),
                ex=self._article_ttl,
            )
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------
    # Generic raw get/set (used by EmbeddingService for vector caching)
    # ------------------------------------------------------------------

    async def get_raw(self, key: str) -> bytes | None:
        """Generic get by full key."""
        try:
            return await self._redis.get(key)
        except Exception:  # noqa: BLE001
            return None

    async def set_raw(self, key: str, value: str, *, ttl: int = 3600) -> None:
        """Generic set by full key with TTL."""
        try:
            await self._redis.set(key, value, ex=ttl)
        except Exception:  # noqa: BLE001
            pass

    async def health_check(self) -> bool:
        """Return True if Redis is reachable."""
        try:
            return await self._redis.ping()
        except Exception:  # noqa: BLE001
            return False
