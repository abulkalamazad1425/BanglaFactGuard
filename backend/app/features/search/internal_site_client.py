import re
import httpx
from typing import Optional
from bs4 import BeautifulSoup
import structlog
from urllib.parse import urljoin, urlparse
from datetime import date

from app.shared.utils.article_url_heuristics import is_probable_article

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

# Shorter tokens ("এই", "ও") match almost any headline and would let page
# chrome pass the query-relevance check below.
_MIN_TOKEN_CHARS = 3


def _build_keyword_query(raw: str, max_words: int = 8) -> str:

    clean = re.sub(r"site:\S+\s*", "", raw).strip()

    clean = re.sub(r'[?!\'"(){}\[\]<>:;,\u0964\u09f7]', " ", clean)

    clean = re.sub(r"\s+", " ", clean).strip()
    words = clean.split()

    priority_words = [w for w in words if len(w) >= 4]
    short_words = [w for w in words if len(w) < 4]

    selected = (priority_words + short_words)[:max_words]
    return " ".join(selected)


class InternalSiteSearchError(Exception):
    """The outlet's own search page could not be queried."""


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
            # Raise, don't return []: a failed request is not a successful
            # empty search, and S04's outcome accounting must see the
            # difference.
            raise InternalSiteSearchError(
                f"internal site search failed for {domain}: {exc}"
            ) from exc

        soup = BeautifulSoup(html, "html.parser")
        results: list[tuple[str, str]] = []
        index_by_url: dict[str, int] = {}

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].strip()
            if not href or href.startswith(("#", "javascript:", "mailto:")):
                continue

            full_url = urljoin(search_url, href)

            if is_probable_article(full_url, patterns):
                url_domain = urlparse(full_url).netloc.replace("www.", "")
                if (
                    domain
                    and url_domain
                    and domain.replace("www.", "") not in url_domain
                ):
                    continue

                link_text = a_tag.get_text(strip=True)
                if len(link_text) < 8:

                    parent = a_tag.parent
                    for _ in range(4):
                        if parent is None:
                            break
                        if parent.name in ("h1", "h2", "h3", "h4", "li"):
                            parent_text = parent.get_text(strip=True)
                            if len(parent_text) > len(link_text):
                                link_text = parent_text
                            break
                        parent = parent.parent

                existing = index_by_url.get(full_url)
                if existing is not None:
                    # Result cards usually link the same article twice — once
                    # from the thumbnail (no text) and once from the headline.
                    # Keep whichever anchor actually carries the headline,
                    # otherwise the title is lost for every result.
                    if len(link_text) > len(results[existing][1]):
                        results[existing] = (full_url, link_text)
                    continue

                index_by_url[full_url] = len(results)
                results.append((full_url, link_text))
                if len(results) >= _MAX_RESULTS:
                    break

        results = _drop_if_query_independent(results, kw_query, domain)

        logger.debug(
            "internal_site_search_done",
            domain=domain,
            result_count=len(results),
        )
        return results


def _query_tokens(query: str) -> set[str]:
    """Content words from the query, long enough to be worth matching on."""
    return {w for w in re.split(r"\s+", query) if len(w) >= _MIN_TOKEN_CHARS}


def _drop_if_query_independent(
    results: list[tuple[str, str]],
    kw_query: str,
    domain: str | None,
) -> list[tuple[str, str]]:
    """Discard a result set that is really just the page's own chrome.

    Several Bangla outlets serve a `/search` page whose results are filled in
    client-side (a Google CSE embed, or an XHR). A plain GET still returns a
    full page of "latest news" links, and those links match the source's
    `article_url_patterns` perfectly — so they were being accepted as search
    hits. Because this client is the highest-priority provider, that quietly
    pushed a handful of unrelated articles to the front of the evidence
    budget and crowded out the real match from the other providers.

    A genuine result set mentions the query somewhere; page chrome does not.
    So require at least one result whose link text shares a content word with
    the query, and keep only the results that do. If nothing matches, the
    response carried no search results at all and is dropped entirely.
    """
    tokens = _query_tokens(kw_query)
    if not tokens or not results:
        return results

    matched = [
        (url, text) for url, text in results if tokens & _query_tokens(text or "")
    ]

    if not matched:
        logger.warning(
            "internal_site_search_query_independent",
            domain=domain,
            discarded=len(results),
            hint="site /search appears to render results client-side",
        )
        return []

    return matched
