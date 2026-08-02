from __future__ import annotations

import re
import logging
from datetime import date
from urllib.parse import unquote

import httpx
from bs4 import BeautifulSoup
from app.core.exceptions import DDGError

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

    def __init__(self) -> None:
        self.base_url = "https://html.duckduckgo.com/html/"

    async def search_entries(
        self,
        query: str,
        domain: str | None = None,
        published_date: date | None = None,
    ) -> list[tuple[str, str]]:

        clean_query = re.sub(r"site:\S+\s*", "", query).strip()

        if published_date:
            clean_query = f"{clean_query} {published_date.year}"

        search_q = f"site:{domain} {clean_query}" if domain else clean_query

        data = {
            "q": search_q,
            "kl": "bd-bn",
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
                raw_url = url_spans[i].get("href", "") or url_spans[i].get_text(
                    strip=True
                )

                if raw_url.startswith("/l/?uddg="):
                    real_url = unquote(raw_url.split("uddg=")[1].split("&")[0])
                elif raw_url.startswith("http"):
                    real_url = raw_url
                else:

                    display = url_spans[i].get_text(strip=True)
                    if display and "." in display:
                        real_url = f"https://{display.strip()}"
                    else:
                        continue

                entries.append((real_url, title))

            return entries

        except Exception as exc:
            logger.warning(
                "DuckDuckGo search failed for query '%s': %r", search_q[:60], exc
            )
            raise DDGError(f"DuckDuckGo search failed: {exc!r}") from exc
