"""
app/clients/google_rss_client.py
==================================
Async client for Google News RSS search (secondary search provider).

Google News RSS requires no API key, supports site: operator in the query
string, and provides structured feed entries with title, link, and pubDate.

Feed URL format:
    https://news.google.com/rss/search?q={query}&hl=bn&gl=BD&ceid=BD:bn

Design decisions:
- feedparser is synchronous — it is executed in a thread pool via
  `asyncio.get_event_loop().run_in_executor` to avoid blocking the event loop.
- The raw Google News redirect URLs (news.google.com/rss/articles/...) are
  resolved to actual article URLs by following the redirect with a lightweight
  HEAD request.
- Redirect resolution is done concurrently for all results using
  `asyncio.gather`, bounded by a semaphore to prevent overwhelming the event
  loop with too many simultaneous connections.
- A `@sync_retry` decorator is applied to the feedparser call for transient
  network failures (DNS, timeout).
"""

from __future__ import annotations

import asyncio
import logging
import urllib.parse
from datetime import date
from html import unescape
from urllib.parse import urljoin

import feedparser
import httpx
from bs4 import BeautifulSoup

from app.core.config import get_settings
from app.core.exceptions import GoogleRSSError
from app.utils.retry import async_retry

logger = logging.getLogger(__name__)

_SETTINGS = get_settings()
_MAX_CONCURRENT_REDIRECTS = 5  # Semaphore limit for redirect resolution


class GoogleRSSClient:
    """
    Async client for Google News RSS search.

    Uses feedparser (sync, run in executor) to parse the RSS feed, then
    resolves Google's redirect URLs to actual article URLs.
    """

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        """
        Args:
            http_client: Shared async HTTP client for redirect resolution.
        """
        self._client = http_client
        self._base_url = _SETTINGS.search.google_rss_base_url
        self._timeout = _SETTINGS.search.google_rss_timeout_seconds
        self._semaphore = asyncio.Semaphore(_MAX_CONCURRENT_REDIRECTS)

    @async_retry(max_attempts=2, base_wait=1.0, max_wait=5.0)
    async def search(
        self,
        query: str,
        *,
        domain: str | None = None,
        published_date: date | None = None,
    ) -> list[str]:
        """
        Search Google News RSS and return resolved article URLs.

        Args:
            query:          The search query string.
            domain:         If provided, adds `site:` constraint to the query.
            published_date: Currently unused for RSS (Google RSS does not
                            support date filtering in the URL). Included for
                            interface consistency with other providers.

        Returns:
            Ordered list of resolved article URLs.
            Returns empty list if the feed is empty or parsing fails.

        Raises:
            GoogleRSSError: On non-retryable feed fetch failures.
        """
        results = await self.search_entries(
            query,
            domain=domain,
            published_date=published_date,
        )
        return [url for url, _ in results]

    async def search_entries(
        self,
        query: str,
        *,
        domain: str | None = None,
        published_date: date | None = None,
    ) -> list[tuple[str, str | None]]:
        """Search Google News RSS and return URLs with optional titles."""
        constrained_query = f"site:{domain} {query}" if domain else query
        feed_url = self._build_feed_url(constrained_query)

        logger.debug("google_rss_fetching", url=feed_url[:120])

        # Parse feed in thread pool (feedparser is synchronous)
        loop = asyncio.get_event_loop()
        try:
            feed = await loop.run_in_executor(
                None,
                lambda: feedparser.parse(feed_url, request_headers={"User-Agent": "BanglaFactGuard/1.0"}),
            )
        except Exception as exc:
            raise GoogleRSSError(
                message=f"feedparser failed: {exc}",
            ) from exc

        if feed.bozo and not feed.entries:
            logger.warning(
                "google_rss_parse_error",
                bozo_exception=str(feed.bozo_exception) if hasattr(feed, "bozo_exception") else "unknown",
            )
            return []

        # Prefer the publisher URL embedded in the RSS entry. Google News
        # often exposes the original article domain in `source.href`.
        raw_results: list[tuple[str, str | None]] = []
        for entry in feed.entries:
            resolved = self._extract_entry_url(entry)
            if resolved:
                title = entry.get("title")
                raw_results.append((resolved, title if isinstance(title, str) and title.strip() else None))

        if not raw_results:
            return []

        # Resolve Google redirect URLs to actual article URLs concurrently
        resolved = await asyncio.gather(
            *[self._resolve_redirect(url) for url, _ in raw_results],
            return_exceptions=True,
        )

        entries: list[tuple[str, str | None]] = []
        for (url, title), result in zip(raw_results, resolved):
            if isinstance(result, str) and result:
                entries.append((result, title))
            elif isinstance(result, Exception):
                logger.debug("redirect_resolution_failed", error=str(result))

        logger.debug(
            "google_rss_completed",
            query=constrained_query[:80],
            raw_count=len(raw_results),
            resolved_count=len(entries),
        )
        return entries

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_feed_url(self, query: str) -> str:
        """
        Build the Google News RSS feed URL for a query.

        Args:
            query: Search query string (with optional site: constraint).

        Returns:
            Full RSS feed URL with Bangla language and Bangladesh locale.
        """
        params = urllib.parse.urlencode(
            {
                "q": query,
                "hl": "bn",
                "gl": "BD",
                "ceid": "BD:bn",
            }
        )
        return f"{self._base_url}?{params}"

    async def _resolve_redirect(self, google_url: str) -> str:
        """
        Resolve a Google News redirect URL to the actual article URL.

        Google RSS entries use `news.google.com/rss/articles/...` redirect
        URLs. A HEAD request follows the redirect to get the final URL.

        Uses a semaphore to limit concurrent redirect resolutions.

        Args:
            google_url: The Google News redirect URL.

        Returns:
            The final article URL after redirect resolution.
            Returns the original URL as fallback if resolution fails.
        """
        # Non-Google URLs don't need resolution
        if "news.google.com" not in google_url:
            return google_url

        async with self._semaphore:
            last_error: Exception | None = None

            for method_name in ("get", "head"):
                try:
                    request = getattr(self._client, method_name)
                    response = await request(
                        google_url,
                        follow_redirects=True,
                        timeout=5.0,
                        headers={
                            "User-Agent": "BanglaFactGuard/1.0",
                            "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
                        },
                    )
                    final_url = str(response.url)
                    if "news.google.com" not in final_url:
                        return final_url

                    # Some Google News pages keep the redirect in-page. Try to
                    # recover a canonical article URL from the HTML.
                    if method_name == "get" and response.text:
                        canonical = self._extract_canonical_url(response.text, base_url=final_url)
                        if canonical:
                            return canonical
                except Exception as exc:  # noqa: BLE001
                    last_error = exc

            if last_error is not None:
                logger.debug(
                    "redirect_resolution_exception",
                    url=google_url[:80],
                    error=str(last_error),
                )

            # Fallback: return the original redirect URL
            return google_url

    @staticmethod
    def _extract_canonical_url(html_text: str, *, base_url: str) -> str | None:
        """Extract a canonical article URL from a Google News HTML page."""
        try:
            soup = BeautifulSoup(html_text, "html.parser")
            link = soup.find("link", rel="canonical")
            if link and link.get("href"):
                href = unescape(link["href"]).strip()
                if href:
                    return urljoin(base_url, href)

            og_url = soup.find("meta", property="og:url")
            if og_url and og_url.get("content"):
                href = unescape(og_url["content"]).strip()
                if href:
                    return urljoin(base_url, href)
        except Exception:  # noqa: BLE001
            return None

        return None

    @staticmethod
    def _extract_entry_url(entry: dict) -> str | None:
        """Prefer the Google News item link, then fall back to the publisher URL."""
        link = entry.get("link")
        if link:
            return str(link)

        source = entry.get("source") or {}
        source_href = source.get("href") if isinstance(source, dict) else None
        if source_href:
            return str(source_href)

        return None
