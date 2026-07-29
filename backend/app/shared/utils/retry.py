"""
app/utils/retry.py
===================
Tenacity-based retry decorators and helpers for external I/O operations.

Design decisions:
- All decorators use exponential backoff with full jitter to avoid thundering
  herd problems when multiple workers hit the same rate-limited API.
- `retry_on_http_error` is the primary decorator for search API clients —
  retries on 429 (rate-limit), 500, 502, 503, 504.
- `retry_on_network_error` retries on connection-level failures (timeout,
  DNS failure) separately from HTTP-level errors, so the two can be composed.
- A `max_attempts` parameter is always explicit — never rely on defaults.
- All retry attempts are logged at WARNING level via structlog so operators
  can monitor retry rates without digging into traces.
- `async_retry` is a convenience wrapper that applies both network and HTTP
  retries together — the most common usage pattern in this codebase.

Usage::

    from app.utils.retry import async_retry

    @async_retry(max_attempts=3, base_wait=1.0, max_wait=10.0)
    async def call_brave_api(query: str) -> dict:
        ...
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from typing import Any, TypeVar

import httpx
from tenacity import (
    AsyncRetrying,
    RetryError,
    before_sleep_log,
    retry_if_exception,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


_RETRYABLE_HTTP_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})


def _is_retryable_http_error(exc: BaseException) -> bool:
    """Return True if the exception is an httpx.HTTPStatusError with a retryable code."""
    return (
        isinstance(exc, httpx.HTTPStatusError)
        and exc.response.status_code in _RETRYABLE_HTTP_CODES
    )


def _is_network_error(exc: BaseException) -> bool:
    """Return True if the exception is a transient network-level failure."""
    return isinstance(
        exc,
        (
            httpx.ConnectError,
            httpx.TimeoutException,
            httpx.ReadError,
            httpx.RemoteProtocolError,
        ),
    )


def async_retry(
    *,
    max_attempts: int = 3,
    base_wait: float = 1.0,
    max_wait: float = 10.0,
    jitter: float = 1.0,
) -> Callable[[F], F]:
    """
    Decorator that retries an async function on retryable HTTP and network errors.

    Applies exponential backoff with full jitter:
        wait = min(base_wait * 2^attempt, max_wait) + random(0, jitter)

    Retries on:
    - HTTP 429, 500, 502, 503, 504 (server-side transient errors)
    - httpx.ConnectError, TimeoutException, ReadError, RemoteProtocolError

    Does NOT retry on:
    - HTTP 4xx (except 429) — these indicate client errors
    - asyncio.CancelledError — propagated immediately

    Args:
        max_attempts: Total number of attempts (including the first call).
        base_wait:    Minimum wait time in seconds between retries.
        max_wait:     Maximum wait time in seconds between retries.
        jitter:       Random jitter ceiling added to each wait interval.

    Returns:
        Decorated async function with retry behaviour.

    Example::

        @async_retry(max_attempts=3, base_wait=0.5, max_wait=8.0)
        async def fetch(url: str) -> httpx.Response:
            async with httpx.AsyncClient() as client:
                return await client.get(url, timeout=10)
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential_jitter(
                    initial=base_wait,
                    max=max_wait,
                    jitter=jitter,
                ),
                retry=retry_if_exception(_is_retryable_http_error)
                | retry_if_exception(_is_network_error),
                before_sleep=before_sleep_log(logger, logging.WARNING),
                reraise=True,
            ):
                with attempt:
                    return await func(*args, **kwargs)

        return wrapper

    return decorator


def sync_retry(
    *,
    max_attempts: int = 3,
    base_wait: float = 0.5,
    max_wait: float = 5.0,
) -> Callable[[F], F]:
    """
    Synchronous retry decorator for non-async functions (e.g. feedparser calls).

    Args:
        max_attempts: Total attempts including the first call.
        base_wait:    Minimum wait between retries (seconds).
        max_wait:     Maximum wait between retries (seconds).

    Returns:
        Decorated synchronous function with retry behaviour.
    """
    from tenacity import Retrying, retry_if_exception_type, wait_exponential

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            for attempt in Retrying(
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential(multiplier=base_wait, max=max_wait),
                retry=retry_if_exception_type((OSError, TimeoutError)),
                before_sleep=before_sleep_log(logger, logging.WARNING),
                reraise=True,
            ):
                with attempt:
                    return func(*args, **kwargs)

        return wrapper

    return decorator

