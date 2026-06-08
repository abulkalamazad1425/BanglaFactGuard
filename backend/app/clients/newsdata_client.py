"""
app/clients/newsdata_client.py
==============================
Async client for NewsData.io latest news API.
"""

from __future__ import annotations

import structlog
import httpx
from datetime import date

from app.core.config import get_settings
from app.core.exceptions import NewsDataError

logger = structlog.get_logger(__name__)


class NewsDataClient:
    """
    Client for NewsData.io (https://newsdata.io/api/1/latest).
    Uses country=bd and language=bn by default.
    Requires an API key configured in SEARCH_NEWSDATA_API_KEY.
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
        Execute a search using NewsData.io and return (url, title) tuples.

        Args:
            query: The search query string.
            domain: The target domain (e.g., 'prothomalo.com'). NewsData.io accepts domain URLs.
            published_date: Optional publication date to filter by (NewsData doesn't natively support exact date match via free query easily, but we pass query).

        Returns:
            List of (URL, title) tuples.
        """
        api_key = self.settings.newsdata_api_key
        if not api_key:
            raise NewsDataError("NewsData API key is not configured.")

        params = {
            "apikey": api_key,
            "q": query,
            "country": "bd",
            "language": "bn",
        }
        
        # NewsData.io domain parameter accepts domain names (e.g., prothomalo.com)
        if domain:
            # Strip subdomains (like www.) as it might work better, but for now we pass domain as is
            domain_clean = domain.replace("www.", "")
            params["domain"] = domain_clean

        try:
            response = await self.client.get(
                self.settings.newsdata_base_url,
                params=params,
                timeout=self.settings.newsdata_timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") == "error":
                raise NewsDataError(f"NewsData.io API error: {data.get('results', {}).get('message')}")

            results = data.get("results", [])
            entries: list[tuple[str, str]] = []
            
            for item in results[:self.settings.newsdata_max_results]:
                link = item.get("link")
                title = item.get("title", "")
                if link:
                    entries.append((link, title))

            return entries

        except httpx.HTTPStatusError as exc:
            # Catch status errors and log response body for debugging
            err_msg = exc.response.text
            raise NewsDataError(
                f"NewsData API returned {exc.response.status_code}: {err_msg}",
                status_code=exc.response.status_code,
            ) from exc
        except httpx.RequestError as exc:
            raise NewsDataError(f"NewsData network error: {exc}") from exc
