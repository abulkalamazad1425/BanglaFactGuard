"""
app/clients/pygooglenews_client.py
==================================
Async wrapper around the PyGoogleNews synchronous library.

## Features

- Searches Google News RSS via PyGoogleNews (no API key required).
- Applies published_date filter using `after`/`before` params (±7 days).
- Unwraps Google News redirect URLs to get the real article URL.
- Uses lang='bn' and country='BD' for Bangla Bangladesh results.
"""

from __future__ import annotations

import asyncio
import re
from datetime import date, timedelta
from urllib.parse import unquote, urlparse, parse_qs

import structlog
from pygooglenews import GoogleNews

from app.core.config import get_settings
from app.core.exceptions import PyGoogleNewsError

logger = structlog.get_logger(__name__)


def _unwrap_google_url(url: str) -> str:
    """
    Unwrap Google News redirect URLs to extract the real article URL.

    Google News RSS entries often look like:
      https://news.google.com/rss/articles/CBMi...
    or redirect through:
      https://news.google.com/articles/CBMi...

    PyGoogleNews usually resolves these, but some entries may still be
    wrapped. We pass them through as-is — Stage 5 will follow the redirect.
    """
    if "news.google.com" in url:
        # Try to extract real URL from query param
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        if "url" in qs:
            return unquote(qs["url"][0])
    return url


class PyGoogleNewsClient:
    """
    Client for PyGoogleNews.
    Searches Google News via RSS feeds without requiring an API key.
    Initialised with lang='bn' and country='BD'.
    """

    def __init__(self) -> None:
        self.settings = get_settings().search
        self.gn = GoogleNews(lang="bn", country="BD")

    def _sync_search(
        self,
        query: str,
        domain: str | None,
        published_date: date | None,
    ) -> list[tuple[str, str]]:
        """
        Synchronous Google News RSS search.
        Runs in a thread pool via asyncio.to_thread.
        """
        search_q = f"site:{domain} {query}" if domain else query

        # Build date-range filter strings for PyGoogleNews
        kwargs: dict[str, str] = {}
        if published_date:
            after = (published_date - timedelta(days=7)).strftime("%Y-%m-%d")
            before = (published_date + timedelta(days=7)).strftime("%Y-%m-%d")
            kwargs["from_"] = after
            kwargs["to_"] = before

        try:
            results = self.gn.search(search_q, **kwargs)
        except Exception as exc:
            raise PyGoogleNewsError(f"PyGoogleNews search failed: {exc}") from exc

        entries: list[tuple[str, str]] = []
        for item in results.get("entries", [])[: self.settings.pygooglenews_max_results]:
            link = item.get("link", "")
            title = item.get("title", "")
            if not link:
                continue
            real_url = _unwrap_google_url(link)
            entries.append((real_url, title))

        return entries

    async def search_entries(
        self,
        query: str,
        domain: str | None = None,
        published_date: date | None = None,
    ) -> list[tuple[str, str]]:
        """
        Execute a Google News RSS search and return (url, title) tuples.

        Args:
            query:          Search query string.
            domain:         Target domain for site: operator filtering.
            published_date: Optional date — ±7 day window applied to RSS query.

        Returns:
            List of (URL, title) tuples.
        """
        return await asyncio.to_thread(
            self._sync_search, query, domain, published_date
        )
