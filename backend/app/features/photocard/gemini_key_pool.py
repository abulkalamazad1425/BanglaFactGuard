"""Process-wide rotation over the configured Gemini API keys, with per-key
limit tracking (HTTP 429)."""

from __future__ import annotations

import time
from typing import Callable

import httpx

_DEFAULT_MINUTE_BLOCK_S = 60.0
_DEFAULT_DAILY_BLOCK_S = 3600.0
# A key blocked for longer than this is not worth waiting for inside one card.
_MAX_WAIT_FOR_KEY_S = 120.0


def limit_info(response: httpx.Response) -> tuple[bool, float]:
    """(is a per-day quota, seconds until the key may be used again) for a 429."""
    daily, delay = False, None
    try:
        details = (response.json().get("error") or {}).get("details") or []
    except ValueError:
        details = []
    for d in details:
        if not isinstance(d, dict):
            continue
        for v in d.get("violations") or []:
            if "perday" in str(v.get("quotaId", "")).lower():
                daily = True
        retry = str(d.get("retryDelay") or "")
        if retry.endswith("s"):
            try:
                delay = float(retry[:-1])
            except ValueError:
                pass
    if delay is None:
        delay = _DEFAULT_DAILY_BLOCK_S if daily else _DEFAULT_MINUTE_BLOCK_S
    return daily, delay


class GeminiKeyPool:
    """Process-wide rotation over the configured keys. Shared by every card,
    so a key that ran out of its limit is skipped by later cards too until
    its limit resets. Keys themselves are never logged - only their number."""

    def __init__(self, keys: list[str], clock: Callable[[], float] = time.monotonic) -> None:
        self.keys = list(keys)
        self._blocked_until = [0.0] * len(self.keys)
        self._next = 0
        self._clock = clock

    def acquire(self) -> int | None:
        """Index of the next usable key (cycling from the last one used), or
        None when every key is blocked for longer than is worth waiting."""
        now = self._clock()
        n = len(self.keys)
        for step in range(n):
            i = (self._next + step) % n
            if self._blocked_until[i] <= now:
                self._next = i
                return i
        soonest = min(range(n), key=lambda i: self._blocked_until[i])
        if self._blocked_until[soonest] - now <= _MAX_WAIT_FOR_KEY_S:
            self._next = soonest
            return soonest  # a short per-minute limit: the normal backoff covers it
        return None

    def block(self, index: int, seconds: float) -> None:
        self._blocked_until[index] = max(self._blocked_until[index], self._clock() + seconds)
        self._next = (index + 1) % len(self.keys)  # the next call uses the next key

    def has_free_key(self) -> bool:
        now = self._clock()
        return any(until <= now for until in self._blocked_until)


_POOLS: dict[tuple[str, ...], GeminiKeyPool] = {}


def key_pool(keys: list[str]) -> GeminiKeyPool:
    pool = _POOLS.get(tuple(keys))
    if pool is None:
        pool = _POOLS[tuple(keys)] = GeminiKeyPool(keys)
    return pool


def reset_key_pools() -> None:
    """Forget every blocked key (tests, or after a quota upgrade)."""
    _POOLS.clear()
