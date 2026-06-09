"""
app/clients/pygooglenews_client.py
==================================
Async wrapper around the PyGoogleNews synchronous library.
"""

from __future__ import annotations

import asyncio
import structlog
from datetime import date
from pygooglenews import GoogleNews

from app.core.config import get_settings
from app.core.exceptions import PyGoogleNewsError

logger = structlog.get_logger(__name__)


class PyGoogleNewsClient:
    """
    Client for PyGoogleNews.
    Searches Google News via its RSS feeds without requiring an API key.
    Initialises with lang='bn' and country='BD'.
    """

    def __init__(self) -> None:
        self.settings = get_settings().search
        # Initialize GoogleNews for Bangla and Bangladesh
        self.gn = GoogleNews(lang='bn', country='BD')

    def _sync_search(self, query: str, domain: str | None) -> list[tuple[str, str]]:
        """Synchronous method to execute the search."""
        # Use site operator if domain is provided
        search_q = f"site:{domain} {query}" if domain else query
        
        try:
            results = self.gn.search(search_q)
            entries = []
            for item in results.get('entries', [])[:self.settings.pygooglenews_max_results]:
                link = item.get('link')
                title = item.get('title', '')
                if link:
                    entries.append((link, title))
            return entries
        except Exception as exc:
            raise PyGoogleNewsError(f"PyGoogleNews search failed: {exc}") from exc

    async def search_entries(
        self,
        query: str,
        domain: str | None = None,
        published_date: date | None = None,
    ) -> list[tuple[str, str]]:
        """
        Execute a search using PyGoogleNews and return (url, title) tuples.

        Args:
            query: The search query string.
            domain: The target domain (e.g., 'prothomalo.com').
            published_date: Optional publication date to filter by.

        Returns:
            List of (URL, title) tuples.
        """
        # Run the synchronous search in a thread to avoid blocking the event loop
        return await asyncio.to_thread(self._sync_search, query, domain)
