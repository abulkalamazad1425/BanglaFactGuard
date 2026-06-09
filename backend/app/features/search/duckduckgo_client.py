"""
app/features/search/duckduckgo_client.py
========================================
Lightweight DuckDuckGo HTML scraper for fallback search.
"""

from __future__ import annotations

import logging
from datetime import date

import httpx
from bs4 import BeautifulSoup
from app.core.exceptions import SearchError

logger = logging.getLogger(__name__)

class DuckDuckGoClient:
    """
    Client for standard web searches via DuckDuckGo HTML.
    Uses httpx and BeautifulSoup4 to extract organic results without API keys.
    """

    def __init__(self) -> None:
        self.base_url = "https://html.duckduckgo.com/html/"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9,bn;q=0.8",
        }

    async def search_entries(
        self,
        query: str,
        domain: str | None = None,
        published_date: date | None = None,
    ) -> list[tuple[str, str]]:
        search_q = f"site:{domain} {query}" if domain else query
        
        data = {
            "q": search_q,
            "kl": "bd-bn",  # region/language preference (Bangladesh/Bengali)
        }
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    self.base_url,
                    data=data,
                    headers=self.headers,
                    follow_redirects=True
                )
                response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            results = soup.find_all("a", class_="result__url", href=True)
            titles = soup.find_all("a", class_="result__snippet") # Sometimes result__a is better, let's use snippet or find parent
            # Actually, standard result anchors have class "result__url" and the title is "result__a"
            title_anchors = soup.find_all("a", class_="result__a")
            
            entries = []
            for i in range(min(len(results), len(title_anchors), 10)):
                url = results[i]["href"]
                title = title_anchors[i].get_text(strip=True)
                
                if url.startswith("/l/?uddg="):
                    from urllib.parse import unquote
                    real_url = unquote(url.split("uddg=")[1].split("&")[0])
                    entries.append((real_url, title))
                elif url.startswith("http"):
                    entries.append((url, title))
                    
            return entries

        except Exception as exc:
            logger.warning("DuckDuckGo search failed for query '%s': %s", search_q[:40], exc)
            raise SearchError(f"DuckDuckGo search failed: {exc}") from exc
