"""
app/features/search/duckduckgo_client.py
========================================
Lightweight DuckDuckGo HTML scraper for fallback search.

## Strategy

Uses DuckDuckGo's HTML endpoint (no API key required).
Sends `site:domain query` for source-constrained searches.
Parses result__a (title) and result__url (URL) from the HTML response.
"""

from __future__ import annotations

import re
import logging
from datetime import date
from urllib.parse import unquote

import httpx
from bs4 import BeautifulSoup
from app.core.exceptions import SearchError

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "bn-BD,bn;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="124", "Google Chrome";v="124"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}


class DuckDuckGoClient:
    """
    Client for standard web searches via DuckDuckGo HTML.
    Uses httpx + BeautifulSoup4 — no API key required.
    """

    def __init__(self) -> None:
        self.base_url = "https://html.duckduckgo.com/html/"

    async def search_entries(
        self,
        query: str,
        domain: str | None = None,
        published_date: date | None = None,
    ) -> list[tuple[str, str]]:
        """
        Execute a DuckDuckGo HTML search and return (url, title) tuples.

        Args:
            query:          Search query (may already include site: operator).
            domain:         Target domain — added as site: if not already present.
            published_date: Optional date — year appended to query if provided.

        Returns:
            List of (URL, title) tuples (at most 10 results).
        """
        # Strip any existing site: and rebuild cleanly
        clean_query = re.sub(r'site:\S+\s*', '', query).strip()

        if published_date:
            clean_query = f"{clean_query} {published_date.year}"

        search_q = f"site:{domain} {clean_query}" if domain else clean_query

        data = {
            "q": search_q,
            "kl": "bd-bn",   # Bangladesh / Bengali region
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    self.base_url,
                    data=data,
                    headers=_HEADERS,
                    follow_redirects=True,
                )
                response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            title_anchors = soup.find_all("a", class_="result__a")
            url_spans = soup.find_all("a", class_="result__url")

            entries: list[tuple[str, str]] = []

            for i in range(min(len(title_anchors), len(url_spans), 10)):
                title = title_anchors[i].get_text(strip=True)
                raw_url = url_spans[i].get("href", "") or url_spans[i].get_text(strip=True)

                # Unwrap DDG redirect URLs
                if raw_url.startswith("/l/?uddg="):
                    real_url = unquote(raw_url.split("uddg=")[1].split("&")[0])
                elif raw_url.startswith("http"):
                    real_url = raw_url
                else:
                    # Build absolute URL from displayed text (DDG sometimes shows naked domain)
                    display = url_spans[i].get_text(strip=True)
                    if display and "." in display:
                        real_url = f"https://{display.strip()}"
                    else:
                        continue

                entries.append((real_url, title))

            return entries

        except Exception as exc:
            logger.warning("DuckDuckGo search failed for query '%s': %s", search_q[:60], exc)
            raise SearchError(f"DuckDuckGo search failed: {exc}") from exc
