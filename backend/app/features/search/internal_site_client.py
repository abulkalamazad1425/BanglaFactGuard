"""
app/features/search/internal_site_client.py
===========================================
Client for directly querying the internal search endpoints of recognized Bangla news sites.
"""

import httpx
import re
from typing import Optional
from bs4 import BeautifulSoup
import structlog
from urllib.parse import urljoin
from datetime import date

from app.features.verification.pipeline.source_registry import SOURCE_REGISTRY

logger = structlog.get_logger(__name__)

class InternalSiteSearchClient:
    """
    Client that scrapes the internal search result page of recognized Bangla news sites.
    """

    def __init__(self, async_client: httpx.AsyncClient) -> None:
        self.client = async_client

    async def search_entries(
        self,
        query: str,
        domain: Optional[str] = None,
        published_date: Optional[date] = None,
    ) -> list[tuple[str, str]]:
        """
        Fetch search results directly from the site's search page.

        Returns:
            List of (url, title_snippet) tuples.
        """
        if not domain or domain not in SOURCE_REGISTRY:
            return []

        config = SOURCE_REGISTRY[domain]
        search_url = config["internal_search_url"].format(query=query)
        patterns = config["article_url_patterns"]

        try:
            response = await self.client.get(
                search_url, 
                timeout=10.0,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                }
            )
            response.raise_for_status()
            html = response.content.decode('utf-8', errors='replace')
        except Exception as exc:
            logger.warning("internal_site_search_failed", domain=domain, error=str(exc))
            return []

        soup = BeautifulSoup(html, "html.parser")
        results = []
        seen_urls = set()

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            full_url = urljoin(search_url, href)

            # Check if URL matches any pattern
            if any(re.search(pattern, full_url) for pattern in patterns):
                if full_url not in seen_urls:
                    seen_urls.add(full_url)
                    title = a_tag.get_text(strip=True)
                    results.append((full_url, title))

        return results
