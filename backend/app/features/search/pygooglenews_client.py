
from __future__ import annotations

import asyncio
import re
from datetime import date, timedelta
from urllib.parse import unquote, urlparse, parse_qs

import structlog
from pygooglenews import GoogleNews

from app.core.config import get_settings
from app.core.exceptions import PyGoogleNewsError

logger = structlog.get_logger(__name__)


def _unwrap_google_url(url: str) -> str:
    if "news.google.com" in url:

        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        if "url" in qs:
            return unquote(qs["url"][0])
    return url


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
        search_q = f"site:{domain} {query}" if domain else query


        kwargs: dict[str, str] = {}
        if published_date:
            after = (published_date - timedelta(days=7)).strftime("%Y-%m-%d")
            before = (published_date + timedelta(days=7)).strftime("%Y-%m-%d")
            kwargs["from_"] = after
            kwargs["to_"] = before

        try:
            results = self.gn.search(search_q, **kwargs)
        except Exception as exc:
            raise PyGoogleNewsError(f"PyGoogleNews search failed: {exc}") from exc

        entries: list[tuple[str, str]] = []
        for item in results.get("entries", [])[: self.settings.pygooglenews_max_results]:
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
                await context.route("**/*.{png,jpg,jpeg,gif,webp,svg,ico,woff,woff2,ttf,mp4,mp3}", lambda route: route.abort())

                async def resolve_one(url: str) -> tuple[str, str]:
                    page = await context.new_page()
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=12000)
                        await page.wait_for_timeout(2000)
                        final_url = page.url
                        logger.debug("pgn_resolved_url", orig=url[:60], final=final_url[:60])
                        return url, final_url
                    except Exception as exc:
                        logger.warning("pgn_resolve_failed", url=url[:60], error=str(exc))
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
