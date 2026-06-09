"""
app/clients/brave_client.py
============================
Async HTTP client for the Brave Search API.

Brave Search is the primary search provider (highest result quality,
supports site: operator, returns structured JSON).

API reference: https://api.search.brave.com/app/documentation/web-search

Design decisions:
- A single `httpx.AsyncClient` is reused across requests (connection pooling).
  It is created at DI time (lifespan) and shared across all concurrent requests.
- All requests are constrained to `site:{domain}` via the `q` parameter to
  ensure source-specific retrieval.
- Rate-limit (429) and server errors (5xx) are retried via `@async_retry`.
- The client raises `BraveAPIError` on non-retryable failures, which the
  Stage 4 orchestration catches and falls through to the next provider.
- `freshness` parameter is optionally set when `published_date` is known,
  narrowing results to a 7-day window around the claimed publication date.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

import httpx

from app.core.config import get_settings
from app.core.exceptions import BraveAPIError
from app.shared.utils.retry import async_retry

logger = logging.getLogger(__name__)

_SETTINGS = get_settings()


class BraveSearchClient:
    """
    Async client for the Brave Search Web Search API.

    Attributes:
        api_key:      Brave Search API key (from settings).
        base_url:     API endpoint URL.
        results_per_query: Number of results to request per query.
        timeout:      Request timeout in seconds.
    """

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        """
        Args:
            http_client: Shared async HTTP client (injected via DI).
                         Must have the Brave API key pre-configured in headers.
        """
        self._client = http_client
        self._api_key = _SETTINGS.search.brave_api_key
        self._base_url = _SETTINGS.search.brave_base_url
        self._results_per_query = _SETTINGS.search.brave_results_per_query
        self._timeout = _SETTINGS.search.brave_timeout_seconds

    @async_retry(max_attempts=3, base_wait=1.0, max_wait=8.0)
    async def search(
        self,
        query: str,
        *,
        domain: str | None = None,
        published_date: date | None = None,
    ) -> list[str]:
        """
        Execute a Brave Search query and return a list of result URLs.

        Args:
            query:          The search query string.
            domain:         If provided, constrains results to this domain
                            using the `site:` operator.
            published_date: If provided, adds a freshness filter within a
                            ±7-day window of the claimed publication date.

        Returns:
            Ordered list of result URLs (most relevant first).
            Returns empty list if no results are found (not an error).

        Raises:
            BraveAPIError: On non-retryable API failures (4xx except 429).
        """
        if not self._api_key:
            raise BraveAPIError(
                message="Brave API key is not configured. Set SEARCH_BRAVE_API_KEY.",
            )

        # Build the constrained query
        search_query = f"site:{domain} {query}" if domain else query

        params: dict[str, str | int] = {
            "q": search_query,
            "count": self._results_per_query,
            "search_lang": "bn",
            "ui_lang": "bn",
            "text_decorations": "false",
            "spellcheck": "false",
        }

        # Add freshness filter when publication date is known
        if published_date:
            params["freshness"] = self._build_freshness_param(published_date)

        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self._api_key,
        }

        try:
            response = await self._client.get(
                self._base_url,
                params=params,
                headers=headers,
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 401:
                raise BraveAPIError(
                    message="Brave API authentication failed. Check SEARCH_BRAVE_API_KEY.",
                    status_code=status,
                ) from exc
            if status == 422:
                raise BraveAPIError(
                    message=f"Brave API rejected query: {search_query!r}",
                    status_code=status,
                ) from exc
            # 429/5xx are retried by @async_retry decorator; re-raise for it
            raise

        data = response.json()
        urls = self._extract_urls(data)

        logger.debug(
            "brave_search_completed",
            query=search_query[:80],
            result_count=len(urls),
        )
        return urls

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_urls(response_data: dict) -> list[str]:
        """
        Extract result URLs from the Brave Search API response JSON.

        Args:
            response_data: Parsed JSON response from the Brave API.

        Returns:
            List of URLs from the `web.results` array.
        """
        try:
            web = response_data.get("web", {})
            results = web.get("results", [])
            return [r["url"] for r in results if "url" in r]
        except (KeyError, TypeError):
            return []

    @staticmethod
    def _build_freshness_param(published_date: date) -> str:
        """
        Build the Brave Search `freshness` parameter for a date window.

        Creates a ±7-day window around `published_date` in the format
        expected by the Brave API: `pd_start:pd_end` (YYYY-MM-DDT00:00:00)

        Args:
            published_date: The alleged publication date of the article.

        Returns:
            Freshness string for the Brave API `freshness` parameter.
        """
        start = published_date - timedelta(days=7)
        end = published_date + timedelta(days=7)
        return f"{start.isoformat()}to{end.isoformat()}"

