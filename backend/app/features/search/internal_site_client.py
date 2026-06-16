"""
app/features/search/internal_site_client.py
===========================================
Client for directly querying the internal search endpoints of recognised Bangla
news sites using the source registry's internal_search_url template.

## Query strategy

Internal site search engines often fail on long, punctuation-heavy Bangla
headlines. This client:
  1. Strips any site: operators from the query string.
  2. Removes Bengali/English punctuation that breaks search backends.
  3. Sends only the top 6 keywords (not the full headline).

## URL extraction

The scraper looks for <a> tags whose href matches any of the site's
article_url_patterns. It also inspects parent <h1>/<h2>/<h3>/<h4> elements
to improve title extraction quality.

## Result limit

At most 10 URLs are returned per search to avoid overwhelming Stage 5.
"""

import re
import httpx
from typing import Optional
from bs4 import BeautifulSoup
import structlog
from urllib.parse import urljoin, urlparse
from datetime import date

logger = structlog.get_logger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "bn-BD,bn;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

_MAX_RESULTS = 15


def _build_keyword_query(raw: str, max_words: int = 8) -> str:
    """
    Strip site: operators and punctuation, return only the top N words.
    Prioritizes longer tokens (likely proper nouns/named entities) over
    short functional words, because proper nouns are the most discriminative
    signal for finding the specific article on the site's search engine.
    """
    # Remove site: operator
    clean = re.sub(r'site:\S+\s*', '', raw).strip()
    # Remove common punctuation that breaks Bangla search backends.
    # \u0964 = Bangla danda (।), \u09f7 = Bangla currency numerator (৷)
    clean = re.sub(r'[?!\'"(){}\[\]<>:;,\u0964\u09f7]', ' ', clean)
    # Collapse whitespace
    clean = re.sub(r'\s+', ' ', clean).strip()
    words = clean.split()

    # Prioritize longer words (4+ chars) - these are more likely to be
    # proper nouns and named entities (like ইয়ামালকে, ফোউজি, মরক্কো)
    # rather than common function words (like গিয়ে, তার, হয়ে)
    priority_words = [w for w in words if len(w) >= 4]
    short_words = [w for w in words if len(w) < 4]

    # Build query: take priority words first, then fill with short words if needed
    selected = (priority_words + short_words)[:max_words]
    return ' '.join(selected)


class InternalSiteSearchClient:
    """
    Client that scrapes the internal search result page of recognised Bangla
    news sites using the internal_search_url from the source registry.
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
        Fetch article URLs from the site's own search endpoint.

        Args:
            query:         Search query (will be keyword-simplified internally).
            domain:        Target domain (e.g. 'prothomalo.com').
            published_date: Ignored — internal search has no reliable date filter.
            source_config:  Source registry config dict with internal_search_url
                            and article_url_patterns.

        Returns:
            List of (url, title_snippet) tuples (at most _MAX_RESULTS entries).
        """
        if not source_config or not source_config.get("internal_search_url"):
            return []

        kw_query = _build_keyword_query(query, max_words=6)
        if not kw_query:
            return []

        search_url = source_config["internal_search_url"].format(query=kw_query)
        patterns: list[str] = source_config.get("article_url_patterns", [])

        logger.debug(
            "internal_site_search",
            domain=domain,
            search_url=search_url[:80],
            kw_query=kw_query,
        )

        try:
            response = await self.client.get(
                search_url,
                timeout=12.0,
                headers=_HEADERS,
                follow_redirects=True,
            )
            response.raise_for_status()
            html = response.content.decode("utf-8", errors="replace")
        except Exception as exc:
            logger.warning("internal_site_search_failed", domain=domain, error=str(exc))
            return []

        soup = BeautifulSoup(html, "html.parser")
        results: list[tuple[str, str]] = []
        seen_urls: set[str] = set()

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].strip()
            if not href or href.startswith(("#", "javascript:", "mailto:")):
                continue

            full_url = urljoin(search_url, href)

            # Validate it matches a known article URL pattern
            if not patterns or any(re.search(pat, full_url) for pat in patterns):
                if full_url in seen_urls:
                    continue

                # Domain guard — never return off-site URLs
                url_domain = urlparse(full_url).netloc.replace("www.", "")
                if domain and url_domain and domain.replace("www.", "") not in url_domain:
                    continue

                seen_urls.add(full_url)

                # Try to get a meaningful title from the link text or nearest heading
                link_text = a_tag.get_text(strip=True)
                if len(link_text) < 8:
                    # Walk up DOM to find a heading parent
                    parent = a_tag.parent
                    for _ in range(4):
                        if parent is None:
                            break
                        if parent.name in ("h1", "h2", "h3", "h4", "li"):
                            link_text = parent.get_text(strip=True)
                            break
                        parent = parent.parent

                results.append((full_url, link_text))
                if len(results) >= _MAX_RESULTS:
                    break

        logger.debug(
            "internal_site_search_done",
            domain=domain,
            result_count=len(results),
        )
        return results
