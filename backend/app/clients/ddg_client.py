"""
app/clients/ddg_client.py
==========================
Async DuckDuckGo search client — tertiary fallback provider.

DuckDuckGo requires no API key but rate-limits aggressively. It is used
only when both Brave and Google RSS are unavailable or return zero results.

Implementation: DuckDuckGo's HTML search endpoint is scraped using httpx
+ BeautifulSoup4. This is the only officially supported non-API method.

Design decisions:
- Randomised User-Agent rotation prevents trivial bot detection.
- A conservative timeout (15 s) and low concurrency avoids triggering
  DuckDuckGo's aggressive rate-limiting.
- The `site:` operator is embedded in the query string (DDG honours it).
- Only organic result links are extracted (DDG "result__a" anchors) —
  ad links and "duckduckgo.com" internal links are filtered out.
- On any failure, raises `DDGError` so Stage 4 can record and skip.
"""

from __future__ import annotations

import logging
import random
import urllib.parse
from datetime import date

import httpx
from bs4 import BeautifulSoup

from app.core.config import get_settings
from app.core.exceptions import DDGError
from app.utils.retry import async_retry

logger = logging.getLogger(__name__)

_SETTINGS = get_settings()

_USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

_DDG_SEARCH_URL = "https://html.duckduckgo.com/html/"
_DDG_INTERNAL_DOMAINS = frozenset({"duckduckgo.com", "duck.com"})


class DDGClient:
    """
    Async DuckDuckGo HTML scraper for use as a last-resort search fallback.

    Scrapes DuckDuckGo's HTML search interface (html.duckduckgo.com) which
    is more stable and less rate-limited than the main JS-heavy interface.
    """

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        """
        Args:
            http_client: Shared async HTTP client.
        """
        self._client = http_client
        self._timeout = _SETTINGS.search.ddg_timeout_seconds
        self._max_results = _SETTINGS.search.ddg_max_results

    @async_retry(max_attempts=2, base_wait=2.0, max_wait=10.0)
    async def search(
        self,
        query: str,
        *,
        domain: str | None = None,
        published_date: date | None = None,
    ) -> list[str]:
        """
        Perform a DuckDuckGo HTML search and extract result URLs.

        Args:
            query:          The search query string.
            domain:         If provided, adds `site:` operator to the query.
            published_date: Unused (DDG HTML interface does not support date filtering).

        Returns:
            List of result URLs (up to `ddg_max_results`).
            Returns empty list if DDG returns no organic results.

        Raises:
            DDGError: On HTTP errors or HTML parsing failures.
        """
        constrained_query = f"site:{domain} {query}" if domain else query

        headers = {
            "User-Agent": random.choice(_USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "bn-BD,bn;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Referer": "https://duckduckgo.com/",
        }

        # DDG HTML endpoint uses POST with form data
        form_data = {
            "q": constrained_query,
            "b": "",          # No pagination (first page only)
            "kl": "bd-bn",   # Bangladesh Bangla locale
        }

        try:
            response = await self._client.post(
                _DDG_SEARCH_URL,
                data=form_data,
                headers=headers,
                timeout=self._timeout,
                follow_redirects=True,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise DDGError(
                message=f"DuckDuckGo returned HTTP {exc.response.status_code}",
                status_code=exc.response.status_code,
            ) from exc
        except httpx.RequestError as exc:
            raise DDGError(
                message=f"DuckDuckGo network error: {exc}",
            ) from exc

        urls = self._parse_results(response.text)

        logger.debug(
            "ddg_search_completed",
            query=constrained_query[:80],
            result_count=len(urls),
        )
        return urls

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_results(self, html: str) -> list[str]:
        """
        Parse DuckDuckGo HTML search results and extract organic result URLs.

        Args:
            html: Raw HTML response body from DDG.

        Returns:
            List of deduplicated article URLs.
        """
        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception:
            soup = BeautifulSoup(html, "html.parser")

        urls: list[str] = []
        seen: set[str] = set()

        # DDG organic results are anchors with class "result__a"
        for anchor in soup.select("a.result__a"):
            href = anchor.get("href", "")
            if not href:
                continue

            # DDG wraps URLs in a redirect; extract the actual URL
            resolved = self._extract_actual_url(href)
            if not resolved:
                continue

            # Skip DDG internal links and duplicates
            domain_part = urllib.parse.urlparse(resolved).netloc.lower()
            if any(d in domain_part for d in _DDG_INTERNAL_DOMAINS):
                continue
            if resolved in seen:
                continue

            seen.add(resolved)
            urls.append(resolved)

            if len(urls) >= self._max_results:
                break

        return urls

    @staticmethod
    def _extract_actual_url(href: str) -> str | None:
        """
        Extract the real destination URL from a DDG redirect href.

        DDG wraps results as: `/l/?uddg=https%3A%2F%2F...&rut=...`
        We extract the `uddg` query parameter to get the actual URL.

        Args:
            href: Raw href from a DDG result anchor.

        Returns:
            Decoded actual URL, or None if parsing fails.
        """
        if href.startswith("http://") or href.startswith("https://"):
            return href

        try:
            parsed = urllib.parse.urlparse(href)
            params = urllib.parse.parse_qs(parsed.query)
            uddg = params.get("uddg", [None])[0]
            if uddg:
                return urllib.parse.unquote(uddg)
            # Fallback: reconstruct absolute URL
            if href.startswith("/"):
                return f"https://duckduckgo.com{href}"
        except Exception:  # noqa: BLE001
            pass
        return None
