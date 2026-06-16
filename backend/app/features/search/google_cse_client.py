"""
app/clients/google_cse_client.py
================================
Async client for Google Custom Search JSON API.
"""

from __future__ import annotations

import structlog
import httpx
from datetime import date

from app.core.config import get_settings
from app.core.exceptions import GoogleCSEError

logger = structlog.get_logger(__name__)


class GoogleCSEClient:
    """
    Client for Google Custom Search JSON API.
    Requires an API key and a Search Engine ID (cx) configured.
    """

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self.client = http_client
        self.settings = get_settings().search

    async def search_entries(
        self,
        query: str,
        domain: str | None = None,
        published_date: date | None = None,
    ) -> list[tuple[str, str]]:
        """
        Execute a search using Google Custom Search API and return (url, title) tuples.

        Args:
            query: The search query string.
            domain: The target domain (e.g., 'prothomalo.com').
            published_date: Optional publication date.

        Returns:
            List of (URL, title) tuples.
        """
        api_key = self.settings.google_cse_api_key
        cx = self.settings.google_cse_cx

        if not api_key or not cx:
            raise GoogleCSEError("Google Custom Search API key or cx is not configured.")

        # Construct query with site operator if domain is provided
        search_q = f"site:{domain} {query}" if domain else query

        params = {
            "key": api_key,
            "cx": cx,
            "q": search_q,
            "num": min(self.settings.google_cse_max_results, 10)  # max 10 per request
        }

        if published_date:
            from datetime import timedelta
            start_date = (published_date - timedelta(days=7)).strftime("%Y%m%d")
            end_date = (published_date + timedelta(days=7)).strftime("%Y%m%d")
            params["sort"] = f"date:r:{start_date}:{end_date}"

        try:
            response = await self.client.get(
                self.settings.google_cse_base_url,
                params=params,
                timeout=self.settings.google_cse_timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()

            items = data.get("items", [])
            entries: list[tuple[str, str]] = []
            
            for item in items:
                link = item.get("link")
                title = item.get("title", "")
                if link:
                    entries.append((link, title))

            return entries

        except httpx.HTTPStatusError as exc:
            err_msg = exc.response.text
            raise GoogleCSEError(
                f"Google CSE API returned {exc.response.status_code}: {err_msg}",
                status_code=exc.response.status_code,
            ) from exc
        except httpx.RequestError as exc:
            raise GoogleCSEError(f"Google CSE network error: {exc}") from exc
