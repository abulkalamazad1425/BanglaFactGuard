"""Key rotation: a key that reached its limit is skipped (by later cards too)
until it resets; a long block is never waited for."""

import httpx

from app.features.photocard.gemini_key_pool import (
    GeminiKeyPool,
    key_pool,
    limit_info,
    reset_key_pools,
)


def quota_429(quota_id=None, retry=None) -> httpx.Response:
    detail = {}
    if quota_id:
        detail["violations"] = [{"quotaId": quota_id}]
    if retry:
        detail["retryDelay"] = retry
    return httpx.Response(429, json={"error": {"details": [detail, "not-a-dict"]}})


def test_limit_info_tells_daily_from_per_minute_limits():
    assert limit_info(quota_429("GenerateRequestsPerDayPerProjectPerModel-FreeTier")) == (True, 3600.0)
    assert limit_info(quota_429("GenerateRequestsPerMinutePerProjectPerModel", retry="17s")) == (False, 17.0)
    assert limit_info(quota_429(retry="soon")) == (False, 60.0)
    assert limit_info(httpx.Response(429, text="not json")) == (False, 60.0)


def test_keys_rotate_and_blocked_keys_are_skipped_until_they_reset():
    now = [0.0]
    pool = GeminiKeyPool(["a", "b", "c"], clock=lambda: now[0])
    assert pool.acquire() == 0
    pool.block(0, 30)
    assert pool.acquire() == 1 and pool.has_free_key()  # the next call goes to the next key
    pool.block(1, 3600)
    pool.block(2, 3600)
    assert pool.acquire() == 0  # 30 s is short enough to wait for with the normal backoff
    pool.block(0, 3600)
    assert pool.acquire() is None and not pool.has_free_key()  # nothing worth waiting for
    now[0] = 4000
    assert pool.acquire() == 1  # all reset: the cycle continues after the last blocked key


def test_pools_are_shared_per_key_set_until_reset():
    reset_key_pools()
    assert key_pool(["a", "b"]) is key_pool(["a", "b"]) and key_pool(["a"]) is not key_pool(["a", "b"])
    shared = key_pool(["a", "b"])
    reset_key_pools()
    assert key_pool(["a", "b"]) is not shared
