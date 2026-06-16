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
        entries = await asyncio.to_thread(
            self._sync_search, query, domain, published_date
        )

        # Resolve Google News wrapper URLs using Playwright
        wrapped_urls = [u for u, _ in entries if "news.google.com" in u]
        if wrapped_urls:
            resolved_map = await self._resolve_with_playwright(wrapped_urls)
            final_entries = []
            for url, title in entries:
                final_url = resolved_map.get(url, url)
                final_entries.append((final_url, title))
            return final_entries

        return entries

    async def _resolve_with_playwright(self, urls: list[str]) -> dict[str, str]:
        """Resolve Google News JS redirects to get the real article URLs."""
        resolved: dict[str, str] = {}
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.warning("pygooglenews_playwright_not_installed")
            return {}

        async with async_playwright() as pw:
            try:
                browser = await pw.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-blink-features=AutomationControlled",
                    ],
                )
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                )
                await context.route("**/*.{png,jpg,jpeg,gif,webp,svg,ico,woff,woff2,ttf,mp4,mp3}", lambda route: route.abort())

                async def resolve_one(url: str) -> tuple[str, str]:
                    page = await context.new_page()
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=12000)
                        await page.wait_for_timeout(2000)  # Wait for JS redirect
                        final_url = page.url
                        logger.debug("pgn_resolved_url", orig=url[:60], final=final_url[:60])
                        return url, final_url
                    except Exception as exc:
                        logger.warning("pgn_resolve_failed", url=url[:60], error=str(exc))
                        return url, url
                    finally:
                        await page.close()

                tasks = [resolve_one(u) for u in urls]
                results = await asyncio.gather(*tasks)
                for orig, final in results:
                    resolved[orig] = final

                await context.close()
                await browser.close()
            except Exception as exc:
                logger.error("pgn_playwright_error", error=str(exc))

        return resolved
