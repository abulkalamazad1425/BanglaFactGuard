
from __future__ import annotations

import asyncio
import re
import time
from collections import defaultdict
from urllib.parse import urlparse

import httpx
import structlog

from app.core.config import get_settings
from app.core.constants import PipelineStageID
from app.features.verification.pipeline.context import PipelineContext

logger = structlog.get_logger(__name__)

_SETTINGS = get_settings()
_MAX_CONCURRENT_FETCHES = 8
_FETCH_TIMEOUT_HTTPX = 15.0
_FETCH_TIMEOUT_PLAYWRIGHT = 22.0
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_ACCEPT_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "bn-BD,bn;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


_NON_ARTICLE_URL_RE = re.compile(
    r"(google\.com/search|bing\.com/search|bing\.com/news/search)", re.I
)


_JS_SHELL_MARKERS = re.compile(
    r'(<div[^>]+id=["\'"](?:app|root|__next)["\'"]|'
    r'__NEXT_DATA__|__NUXT__|vue-server-renderer|'
    r'data-reactroot|window\.__INITIAL_STATE__)',
    re.I,
)


def _is_shell_html(html: str) -> bool:
    if not _JS_SHELL_MARKERS.search(html):
        return False

    body_text_len = len(re.sub(r"<[^>]+>", "", html))
    return body_text_len < 2000


class EvidenceRetrievalStage:

    stage_id = PipelineStageID.S05_EVIDENCE_RETRIEVAL

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._client = http_client
        self._semaphore = asyncio.Semaphore(_MAX_CONCURRENT_FETCHES)
        self._top_k = _SETTINGS.search.top_k_candidates

        self._domain_last_ts: dict[str, float] = defaultdict(float)
        self._domain_lock: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def execute(self, context: PipelineContext) -> PipelineContext:

        candidates = [
            c for c in context.candidate_urls
            if not _NON_ARTICLE_URL_RE.search(c.url)
        ]


        candidates = [_maybe_deamp(c) for c in candidates]


        candidates = candidates[: self._top_k]

        if not candidates:
            context._raw_html_cache = {}
            return context

        urls = [c.url for c in candidates]

        logger.info(
            "s05_fetching_evidence",
            url_count=len(urls),
            claim_id=str(context.claim_id) if context.claim_id else "pending",
        )


        tier1_tasks = [self._fetch_httpx(url) for url in urls]
        tier1_results = await asyncio.gather(*tier1_tasks, return_exceptions=True)

        raw_html_cache: dict[str, str] = {}
        shell_urls: list[str] = []

        for url, result in zip(urls, tier1_results):
            if isinstance(result, str) and result:
                if _is_shell_html(result):
                    shell_urls.append(url)
                else:
                    raw_html_cache[url] = result
            else:
                context.failed_extraction_urls.append(url)


        if shell_urls:
            logger.info("s05_playwright_needed", count=len(shell_urls))
            pw_results = await self._fetch_playwright_batch(shell_urls)
            for url, html in pw_results.items():
                if html:
                    raw_html_cache[url] = html
                else:
                    context.failed_extraction_urls.append(url)

        context._raw_html_cache = raw_html_cache

        logger.info(
            "s05_retrieval_complete",
            attempted=len(urls),
            tier1_success=len(raw_html_cache) - len(shell_urls),
            tier2_needed=len(shell_urls),
            tier2_success=sum(1 for u in shell_urls if u in raw_html_cache),
            failed=len(context.failed_extraction_urls),
        )
        return context





    async def _fetch_httpx(self, url: str) -> str | Exception:
        domain = urlparse(url).netloc
        async with self._semaphore:

            async with self._domain_lock[domain]:
                elapsed = time.monotonic() - self._domain_last_ts[domain]
                if elapsed < 0.5:
                    await asyncio.sleep(0.5 - elapsed)
                self._domain_last_ts[domain] = time.monotonic()

            try:
                resp = await self._client.get(
                    url,
                    timeout=_FETCH_TIMEOUT_HTTPX,
                    follow_redirects=True,
                    headers=_ACCEPT_HEADERS,
                )
                if 200 <= resp.status_code < 300:
                    return resp.text
                return Exception(f"HTTP {resp.status_code}")
            except httpx.TimeoutException as exc:
                return exc
            except httpx.ConnectError as exc:
                return exc
            except Exception as exc:
                return exc





    async def _fetch_playwright_batch(self, urls: list[str]) -> dict[str, str | None]:
        import sys
        if sys.platform == "win32":
            return await asyncio.to_thread(self._run_playwright_sync, urls)
        return await self._run_playwright_async(urls)

    def _run_playwright_sync(self, urls: list[str]) -> dict[str, str | None]:
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

    async def _run_playwright_async(self, urls: list[str]) -> dict[str, str | None]:
        results: dict[str, str | None] = {}
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.warning("s05_playwright_not_installed")
            return {u: None for u in urls}

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            context_pw = await browser.new_context(
                user_agent=_USER_AGENT,
                locale="bn-BD",
                extra_http_headers={"Accept-Language": "bn-BD,bn;q=0.9,en;q=0.8"},
            )

            await context_pw.route(
                "**/*.{png,jpg,jpeg,gif,webp,svg,ico,woff,woff2,ttf,mp4,mp3}",
                lambda route: route.abort(),
            )

            for url in urls:
                page = await context_pw.new_page()
                try:
                    await page.goto(
                        url,
                        wait_until="domcontentloaded",
                        timeout=int(_FETCH_TIMEOUT_PLAYWRIGHT * 1000),
                    )

                    await page.wait_for_timeout(1500)
                    html = await page.content()
                    results[url] = html if html else None
                    logger.debug("s05_playwright_success", url=url[:80])
                except Exception as exc:
                    logger.warning("s05_playwright_failed", url=url[:80], error=str(exc)[:80])
                    results[url] = None
                finally:
                    await page.close()

            await context_pw.close()
            await browser.close()

        return results






def _maybe_deamp(candidate):
    url = candidate.url
    if "/amp/" in url or url.endswith("/amp"):
        canonical = re.sub(r"/amp(/|$)", "/", url).rstrip("/")

        return candidate.model_copy(update={"url": canonical})
    return candidate