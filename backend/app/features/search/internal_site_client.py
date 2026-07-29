
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

    clean = re.sub(r'site:\S+\s*', '', raw).strip()


    clean = re.sub(r'[?!\'"(){}\[\]<>:;,\u0964\u09f7]', ' ', clean)

    clean = re.sub(r'\s+', ' ', clean).strip()
    words = clean.split()




    priority_words = [w for w in words if len(w) >= 4]
    short_words = [w for w in words if len(w) < 4]


    selected = (priority_words + short_words)[:max_words]
    return ' '.join(selected)


class InternalSiteSearchClient:

    def __init__(self, async_client: httpx.AsyncClient) -> None:
        self.client = async_client

    async def search_entries(
        self,
        query: str,
        domain: Optional[str] = None,
        published_date: Optional[date] = None,
        source_config: Optional[dict] = None,
    ) -> list[tuple[str, str]]:
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


            if not patterns or any(re.search(pat, full_url) for pat in patterns):
                if full_url in seen_urls:
                    continue


                url_domain = urlparse(full_url).netloc.replace("www.", "")
                if domain and url_domain and domain.replace("www.", "") not in url_domain:
                    continue

                seen_urls.add(full_url)


                link_text = a_tag.get_text(strip=True)
                if len(link_text) < 8:

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
