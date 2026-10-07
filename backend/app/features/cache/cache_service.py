from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis
import structlog

from app.core.config import get_settings
from app.core.constants import REDIS_KEY_PREFIX

logger = structlog.get_logger(__name__)
_SETTINGS = get_settings()


_KEY_CLAIM = f"{REDIS_KEY_PREFIX}:claim"
_KEY_SEARCH = f"{REDIS_KEY_PREFIX}:search"


class CacheService:

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self._redis = redis_client
        self._claim_ttl = _SETTINGS.redis.ttl_claim_result
        self._search_ttl = _SETTINGS.redis.ttl_search_result

    async def get_claim_result(self, claim_hash: str) -> bytes | None:
        try:
            return await self._redis.get(f"{_KEY_CLAIM}:{claim_hash}")
        except Exception as exc:
            logger.debug("cache_get_failed", key_prefix=_KEY_CLAIM, error=str(exc))
            return None

    async def set_claim_result(self, claim_hash: str, payload: str) -> None:
        try:
            await self._redis.set(
                f"{_KEY_CLAIM}:{claim_hash}",
                payload,
                ex=self._claim_ttl,
            )
        except Exception as exc:
            logger.debug("cache_set_failed", key_prefix=_KEY_CLAIM, error=str(exc))

    async def set_claim_pointer(self, claim_hash: str, payload: str, *, ttl: int) -> None:
        """Like set_claim_result but with an explicit freshness window (the
        NOT_FOUND window is shorter than the default claim TTL)."""
        try:
            await self._redis.set(f"{_KEY_CLAIM}:{claim_hash}", payload, ex=ttl)
        except Exception as exc:
            logger.debug("cache_set_failed", key_prefix=_KEY_CLAIM, error=str(exc))

    async def invalidate_claim(self, claim_hash: str) -> None:
        try:
            await self._redis.delete(f"{_KEY_CLAIM}:{claim_hash}")
        except Exception:
            pass

    async def get_search_result(
        self, provider: str, query_hash: str
    ) -> list[str] | None:
        try:
            raw = await self._redis.get(f"{_KEY_SEARCH}:{provider}:{query_hash}")
            if raw:
                return json.loads(raw)
            return None
        except Exception:
            return None

    async def set_search_result(
        self, provider: str, query_hash: str, urls: list[str]
    ) -> None:
        try:
            await self._redis.set(
                f"{_KEY_SEARCH}:{provider}:{query_hash}",
                json.dumps(urls),
                ex=self._search_ttl,
            )
        except Exception:
            pass

    async def get_raw(self, key: str) -> bytes | None:
        try:
            return await self._redis.get(key)
        except Exception:
            return None

    async def set_raw(self, key: str, value: str, *, ttl: int = 3600) -> None:
        try:
            await self._redis.set(key, value, ex=ttl)
        except Exception:
            pass

    async def health_check(self) -> bool:
        try:
            return await self._redis.ping()
        except Exception:
            return False
