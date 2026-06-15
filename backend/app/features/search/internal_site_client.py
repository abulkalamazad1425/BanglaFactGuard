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
        source_config: Optional[dict] = None,
    ) -> list[tuple[str, str]]:
        """
        Fetch search results directly from the site's search page.

        Returns:
            List of (url, title_snippet) tuples.
        """
        if not domain or not source_config or not source_config.get("internal_search_url"):
            return []

        clean_query = re.sub(r'site:\S+\s*', '', query).strip()
        search_url = source_config["internal_search_url"].format(query=clean_query)
        patterns = source_config.get("article_url_patterns", [])

        try:
            response = await self.client.get(
                search_url, 
                timeout=10.0,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                    "Accept-Language": "bn-BD,bn;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Cache-Control": "max-age=0",
                    "Upgrade-Insecure-Requests": "1",
                    "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                    "Sec-Ch-Ua-Mobile": "?0",
                    "Sec-Ch-Ua-Platform": '"Windows"',
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
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
