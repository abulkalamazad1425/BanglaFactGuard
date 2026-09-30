from __future__ import annotations

import asyncio
import re
from datetime import date, timedelta
from urllib.parse import (
    parse_qs,
    parse_qsl,
    unquote,
    urlencode,
    urlparse,
    urlunparse,
)

import structlog
from pygooglenews import GoogleNews

from app.core.config import get_settings
from app.core.exceptions import PyGoogleNewsError

logger = structlog.get_logger(__name__)

_SITE_OPERATOR_RE = re.compile(r"\bsite:", re.IGNORECASE)

# Google News indexes a story under its own crawl date, which routinely sits
# a few days off the date printed on the article — and for older stories the
# feed is sparse enough that a tight window returns almost nothing. A +/-7 day
# window cut a 10-result query down to a single hit in testing, so keep the
# window wide enough to survive that skew.
_DATE_WINDOW = timedelta(days=45)

# How long to wait for the Google News interstitial to hop to the publisher.
_REDIRECT_WAIT_MS = 8000

# Date-bounded Google News queries only behave on reasonably fresh stories.
# Past this age the feed answers a bounded query with a near-empty set even
# when the unbounded one returns the article — a claim dated Feb 2025 went
# from ten results to one, losing the article being verified. Older claims
# are better served by an unbounded query, with the date used for ranking.
_DATE_FILTER_MAX_AGE = timedelta(days=180)


def _date_filter_is_useful(published_date: date) -> bool:
    return (date.today() - published_date) <= _DATE_FILTER_MAX_AGE


def _unwrap_google_url(url: str) -> str:
    if "news.google.com" in url:

        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        if "url" in qs:
            return unquote(qs["url"][0])
    return url


def _strip_challenge_params(url: str) -> str:
    """Drop the one-shot token Cloudflare appends after clearing a challenge.

    Landing on a protected article through a browser leaves the URL as
    ...?__cf_chl_rt_tk=<token>. Kept as-is it becomes a second, unusable
    copy of an article already in the candidate set, and is what the user
    would be shown as the source link.
    """
    parsed = urlparse(url)
    if not parsed.query:
        return url
    kept = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if not k.lower().startswith("__cf_")
    ]
    if len(kept) == len(parse_qsl(parsed.query, keep_blank_values=True)):
        return url
    return urlunparse(parsed._replace(query=urlencode(kept)))


class PyGoogleNewsClient:

    def __init__(self) -> None:
        self.settings = get_settings().search
        self.gn = GoogleNews(lang="bn", country="BD")

    def _sync_search(
        self,
        query: str,
        domain: str | None,
        published_date: date | None,
    ) -> list[tuple[str, str]]:
        # S04 already site-restricts the query before handing it over. Adding
        # the operator again produced "site:x site:x ...", which Google News
        # scores worse than the single-operator form.
        if domain and not _SITE_OPERATOR_RE.search(query):
            search_q = f"site:{domain} {query}"
        else:
            search_q = query

        kwargs: dict[str, str] = {}
        if published_date and _date_filter_is_useful(published_date):
            after = (published_date - _DATE_WINDOW).strftime("%Y-%m-%d")
            before = (published_date + _DATE_WINDOW).strftime("%Y-%m-%d")
            kwargs["from_"] = after
            kwargs["to_"] = before

        try:
            results = self.gn.search(search_q, **kwargs)
        except Exception as exc:
            raise PyGoogleNewsError(f"PyGoogleNews search failed: {exc}") from exc

        entries: list[tuple[str, str]] = []
        for item in results.get("entries", [])[
            : self.settings.pygooglenews_max_results
        ]:
            link = item.get("link", "")
            title = item.get("title", "")
            if not link:
                continue
            real_url = _unwrap_google_url(link)
            entries.append((real_url, title))

        return entries

    async def search_entries(
        self,
        query: str,
        domain: str | None = None,
        published_date: date | None = None,
    ) -> list[tuple[str, str]]:
        entries = await asyncio.to_thread(
            self._sync_search, query, domain, published_date
        )

        wrapped_urls = [u for u, _ in entries if "news.google.com" in u]
        if wrapped_urls:
            resolved_map = await self._resolve_with_playwright(wrapped_urls)
            final_entries = []
            for url, title in entries:
                final_url = resolved_map.get(url, url)
                final_entries.append((final_url, title))
            return final_entries

        return entries

    async def _resolve_with_playwright(self, urls: list[str]) -> dict[str, str]:
        import sys

        if sys.platform == "win32":
            return await asyncio.to_thread(self._run_playwright_sync, urls)
        return await self._run_playwright_async(urls)

    def _run_playwright_sync(self, urls: list[str]) -> dict[str, str]:
        import asyncio
        import sys

        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self._run_playwright_async(urls))
        finally:
            loop.close()

    async def _run_playwright_async(self, urls: list[str]) -> dict[str, str]:
        resolved: dict[str, str] = {}
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.warning("pygooglenews_playwright_not_installed")
            return {}

        async with async_playwright() as pw:
            try:
                browser = await pw.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-blink-features=AutomationControlled",
                    ],
                )
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                )
                await context.route(
                    "**/*.{png,jpg,jpeg,gif,webp,svg,ico,woff,woff2,ttf,mp4,mp3}",
                    lambda route: route.abort(),
                )

                # Resolving several redirect pages at once on one browser
                # context causes enough contention that some navigations
                # miss a 12s timeout even though a single page resolves in
                # ~2-3s — cap concurrency and give each page more headroom.
                semaphore = asyncio.Semaphore(4)

                async def resolve_one(url: str) -> tuple[str, str]:
                    async with semaphore:
                        page = await context.new_page()
                        try:
                            await page.goto(
                                url, wait_until="domcontentloaded", timeout=20000
                            )
                            # Google News hands back an interstitial that
                            # redirects to the publisher from JS. A fixed
                            # pause races that redirect — when it loses, the
                            # unresolved news.google.com URL flows on to S04,
                            # where the domain filter silently drops it and
                            # the real article is lost. Wait for the hop.
                            try:
                                await page.wait_for_url(
                                    lambda u: "news.google.com" not in u,
                                    timeout=_REDIRECT_WAIT_MS,
                                )
                            except Exception:
                                await page.wait_for_timeout(2500)
                            final_url = _strip_challenge_params(page.url)
                            if "news.google.com" in final_url:
                                logger.warning(
                                    "pgn_resolve_incomplete", url=url[:60]
                                )
                            logger.debug(
                                "pgn_resolved_url", orig=url[:60], final=final_url[:60]
                            )
                            return url, final_url
                        except Exception as exc:
                            logger.warning(
                                "pgn_resolve_failed", url=url[:60], error=str(exc)
                            )
                            return url, url
                        finally:
                            await page.close()

                tasks = [resolve_one(u) for u in urls]
                results = await asyncio.gather(*tasks)
                for orig, final in results:
                    resolved[orig] = final

                await context.close()
                await browser.close()
            except Exception as exc:
                logger.error("pgn_playwright_error", error=str(exc))

        return resolved
