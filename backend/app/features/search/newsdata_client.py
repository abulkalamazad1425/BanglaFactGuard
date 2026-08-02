from __future__ import annotations

import re
import structlog
import httpx
from datetime import date

from app.core.config import get_settings
from app.core.exceptions import NewsDataError

logger = structlog.get_logger(__name__)


def _shorten_query(query: str, max_words: int = 8) -> str:
    clean = re.sub(r"site:\S+\s*", "", query).strip()
    clean = re.sub(r'[।?!\'"(){}\[\]<>:;,।]', " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    words = clean.split()
    shortened = " ".join(words[:max_words])
    return shortened[:80]


class NewsDataClient:

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self.client = http_client
        self.settings = get_settings().search

    async def search_entries(
        self,
        query: str,
        domain: str | None = None,
        published_date: date | None = None,
    ) -> list[tuple[str, str]]:
        api_key = self.settings.newsdata_api_key
        if not api_key:
            raise NewsDataError("NewsData API key is not configured.")

        short_query = _shorten_query(query, max_words=8)

        if published_date:
            short_query = f"{short_query} {published_date.year}"

        params: dict[str, str | int] = {
            "apikey": api_key,
            "q": short_query,
            "country": "bd",
            "language": "bn",
            "size": self.settings.newsdata_max_results,
        }

        if domain:
            params["domain"] = domain.replace("www.", "")

        logger.debug(
            "newsdata_search",
            query=short_query[:60],
            domain=domain,
        )

        try:
            return await self._request(params)
        except NewsDataError as exc:
            if domain and exc.details.get("code") == "UnsupportedFilter":
                # NewsData's domain registry doesn't cover every Bangla
                # outlet (kalerkantho.com, jugantor.com, etc. are absent).
                # Degrade to an un-scoped keyword search — the caller
                # (SourceSearchStage) already filters every candidate URL
                # down to the target domain afterwards, so this still only
                # surfaces on-domain results, just without NewsData's own
                # filtering doing that work for us.
                logger.info(
                    "newsdata_domain_unsupported_retrying_unscoped", domain=domain
                )
                params.pop("domain", None)
                return await self._request(params)
            raise

    async def _request(self, params: dict[str, str | int]) -> list[tuple[str, str]]:
        try:
            response = await self.client.get(
                self.settings.newsdata_base_url,
                params=params,
                timeout=self.settings.newsdata_timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "error":
                err = data.get("results", {}) or {}
                raise NewsDataError(
                    f"NewsData.io API error: {err}",
                    details={"code": err.get("code")},
                )

            results = data.get("results", [])
            entries: list[tuple[str, str]] = []
            for item in results[: self.settings.newsdata_max_results]:
                link = item.get("link")
                title = item.get("title", "")
                if link:
                    entries.append((link, title))

            return entries

        except httpx.HTTPStatusError as exc:
            # NewsData reports domain-unsupported (and similar) errors via a
            # non-2xx status *and* a JSON body with a `code` field — parse it
            # out so callers (e.g. the domain-fallback retry above) can act
            # on the specific failure reason instead of just the status code.
            code = None
            try:
                code = (exc.response.json().get("results") or {}).get("code")
            except Exception:
                pass
            raise NewsDataError(
                f"NewsData API returned {exc.response.status_code}: {exc.response.text[:200]}",
                status_code=exc.response.status_code,
                details={"code": code} if code else None,
            ) from exc
        except httpx.RequestError as exc:
            raise NewsDataError(f"NewsData network error: {exc}") from exc
