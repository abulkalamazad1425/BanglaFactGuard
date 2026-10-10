"""Redis wrapper: namespaced keys with TTLs, and Redis trouble is never an error."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

from app.core.constants import REDIS_KEY_PREFIX
from app.features.cache.cache_service import CacheService


class FakeRedis:
    def __init__(self):
        self.store, self.ttl = {}, {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ex=None):
        self.store[key], self.ttl[key] = value, ex

    async def delete(self, key):
        self.store.pop(key, None)

    async def ping(self):
        return True


async def test_claims_searches_and_raw_values_round_trip_with_ttls():
    redis = FakeRedis()
    cache = CacheService(redis)
    await cache.set_claim_result("h", "payload")
    assert await cache.get_claim_result("h") == "payload"
    assert redis.ttl[f"{REDIS_KEY_PREFIX}:claim:h"] == cache._claim_ttl
    await cache.set_claim_pointer("h", "pointer", ttl=60)
    assert redis.ttl[f"{REDIS_KEY_PREFIX}:claim:h"] == 60
    await cache.invalidate_claim("h")
    assert await cache.get_claim_result("h") is None

    await cache.set_search_result("py_google_news", "q", [["https://a/1", "t"]])
    assert await cache.get_search_result("py_google_news", "q") == [["https://a/1", "t"]]
    assert json.loads(redis.store[f"{REDIS_KEY_PREFIX}:search:py_google_news:q"]) == [["https://a/1", "t"]]
    assert await cache.get_search_result("py_google_news", "missing") is None

    await cache.set_raw("k", "v", ttl=5)
    assert await cache.get_raw("k") == "v" and redis.ttl["k"] == 5
    assert await cache.health_check() is True


async def test_an_unavailable_redis_degrades_to_cache_misses():
    broken = MagicMock(**{name: AsyncMock(side_effect=ConnectionError("redis down"))
                          for name in ("get", "set", "delete", "ping")})
    cache = CacheService(broken)
    assert await cache.get_claim_result("h") is None
    assert await cache.get_search_result("p", "q") is None
    assert await cache.get_raw("k") is None
    assert await cache.health_check() is False
    for call in (cache.set_claim_result("h", "x"), cache.set_claim_pointer("h", "x", ttl=1), cache.invalidate_claim("h"),
                 cache.set_search_result("p", "q", []), cache.set_raw("k", "v")):
        await call  # never raises
