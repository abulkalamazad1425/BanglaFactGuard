from __future__ import annotations

import asyncio
import re
import threading
import time
from collections import defaultdict
from urllib.parse import urlparse

import httpx
import structlog

from app.core.config import get_settings
from app.core.constants import PipelineStageID
from app.features.verification.pipeline.context import PipelineContext
from app.shared.utils.domains import allowed_domains_for, is_allowed_host

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
    r"__NEXT_DATA__|__NUXT__|vue-server-renderer|"
    r"data-reactroot|window\.__INITIAL_STATE__)",
    re.I,
)

_BOT_WALL_MARKERS = re.compile(
    r"(Just a moment\.\.\.|Attention Required!|cf-browser-verification|"
    r"challenge-platform|Checking your browser|Enable JavaScript and cookies)",
    re.I,
)

# Statuses an anti-bot layer returns for a page a browser can load fine.
_RETRY_IN_BROWSER_STATUSES = frozenset({401, 403, 406, 429, 503})

# Cloudflare's managed challenge on these outlets takes the best part of ten
# seconds to hand over the real page; a shorter budget captures the
# interstitial and the article is scored as if it had no content.
_BOT_WALL_RETRIES = 5
_BOT_WALL_WAIT_MS = 3000

# Pages open in one shared browser context; a handful at a time keeps the
# challenge wait overlapping without starving each page of CPU.
_PLAYWRIGHT_CONCURRENCY = 4

# A host whose challenge did not clear is left alone for a while. Re-opening
# its pages in a browser, each reloaded several times, is exactly the traffic
# that makes Cloudflare escalate from a passive check to a hard block for this
# IP; backing off lets the IP's reputation recover. Process-wide; the browser
# runs in its own thread on Windows, hence the lock.
_WALL_COOLDOWN_S = 600.0
_walled_until: dict[str, float] = {}
_walled_lock = threading.Lock()


def _host_cooling_down(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    with _walled_lock:
        until = _walled_until.get(host)
        if until is None:
            return False
        if until <= time.monotonic():
            del _walled_until[host]
            return False
        return True


def _mark_walled(url: str) -> None:
    host = (urlparse(url).hostname or "").lower()
    with _walled_lock:
        _walled_until[host] = time.monotonic() + _WALL_COOLDOWN_S


_SCRIPT_STYLE_RE = re.compile(
    r"<(script|style|noscript)\b[^>]*>.*?</\1>", re.I | re.S
)


def _visible_text_len(html: str) -> int:
    """Length of the text a reader would actually see.

    Stripping tags alone leaves the *contents* of <script>/<style> behind,
    which on a challenge page runs to tens of thousands of characters and
    makes an almost text-free interstitial look like a full article.
    """
    without_code = _SCRIPT_STYLE_RE.sub(" ", html)
    return len(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", without_code)).strip())


def _is_shell_html(html: str) -> bool:
    if not _JS_SHELL_MARKERS.search(html):
        return False

    return _visible_text_len(html) < 2000


def _is_bot_wall(html: str) -> bool:
    """Detect an anti-bot interstitial served with a 200.

    Cloudflare leaves its challenge script on ordinary pages too, so the
    marker alone is not enough — a real article would be re-fetched in a
    browser for nothing. An interstitial also carries almost no text, so
    require both signals.
    """
    if not _BOT_WALL_MARKERS.search(html):
        return False
    return _visible_text_len(html) < 2000


class _OriginBlocked(Exception):
    """The origin refused the plain HTTP client, not the URL itself.

    Several outlets (bd-pratidin, kalerkantho, jugantor) sit behind Cloudflare
    bot protection that rejects httpx on its TLS fingerprint alone — the same
    URL loads fine in a real browser. Treated as "retry in Playwright" rather
    than a dead URL, which is what it looked like before.
    """

    def __init__(self, status: int) -> None:
        super().__init__(f"origin blocked request (HTTP {status})")
        self.status = status


class _RedirectRejected(Exception):
    """The request ended on a host outside the claimed source's registered
    domains/channels (open redirect, shortener, syndication partner). The page
    is NOT evidence from the claimed source, so it is dropped - and it is a
    rejected candidate, not a fetch failure."""

    def __init__(self, final_url: str) -> None:
        super().__init__(f"final URL left the claimed source: {final_url}")
        self.final_url = final_url


_REJECTED = "__REDIRECT_REJECTED__"


class EvidenceRetrievalStage:

    stage_id = PipelineStageID.S05_EVIDENCE_RETRIEVAL

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._client = http_client
        self._semaphore = asyncio.Semaphore(_MAX_CONCURRENT_FETCHES)
        self._top_k = _SETTINGS.search.top_k_candidates

        self._allowed: list[str] = []
        self._domain_last_ts: dict[str, float] = defaultdict(float)
        self._domain_lock: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def execute(self, context: PipelineContext) -> PipelineContext:

        candidates = [
            c for c in context.candidate_urls if not _NON_ARTICLE_URL_RE.search(c.url)
        ]

        candidates = [_maybe_deamp(c) for c in candidates]

        candidates = candidates[: self._top_k]

        if context.is_verified_sources_mode:
            scope = context.verified_scope
            self._allowed = scope.all_domains if scope is not None else []
            # An empty allowlist would mean "unrestricted" below - in this mode
            # it means nothing is eligible, so nothing is fetched.
            candidates = [
                c for c in candidates
                if self._allowed and is_allowed_host(urlparse(c.url).hostname or "", self._allowed)
            ]
        else:
            self._allowed = allowed_domains_for(
                context.normalized_source, getattr(context, "source_config", None)
            )

        if not candidates:
            context.fetched_html = {}
            return context

        urls = [c.url for c in candidates]

        logger.info(
            "s05_fetching_evidence",
            url_count=len(urls),
            submission_id=str(context.submission_id) if context.submission_id else "pending",
        )

        tier1_tasks = [self._fetch_httpx(url) for url in urls]
        tier1_results = await asyncio.gather(*tier1_tasks, return_exceptions=True)

        raw_html_cache: dict[str, str] = {}
        shell_urls: list[str] = []
        rejected = 0

        for url, result in zip(urls, tier1_results):
            if isinstance(result, _RedirectRejected):
                rejected += 1
                logger.warning("s05_redirect_rejected", url=url[:80], final=result.final_url[:80])
            elif isinstance(result, str) and result:
                if _is_shell_html(result) or _is_bot_wall(result):
                    shell_urls.append(url)
                else:
                    raw_html_cache[url] = result
            elif isinstance(result, _OriginBlocked):
                # A browser can still load this — don't write the URL off.
                shell_urls.append(url)
            else:
                context.failed_extraction_urls.append(url)

        if shell_urls:
            logger.info("s05_playwright_needed", count=len(shell_urls))
            pw_results = await self._fetch_playwright_batch(shell_urls)
            for url, html in pw_results.items():
                if html == _REJECTED:
                    rejected += 1
                elif html:
                    raw_html_cache[url] = html
                else:
                    context.failed_extraction_urls.append(url)

        context.fetched_html = raw_html_cache
        context.search_redirect_rejected += rejected
        context.fetch_attempted += len(urls) - rejected
        context.fetch_errors += len(context.failed_extraction_urls)

        tier2_success = sum(1 for u in shell_urls if u in raw_html_cache)
        logger.info(
            "s05_retrieval_complete",
            attempted=len(urls),
            tier1_success=len(raw_html_cache) - tier2_success,
            tier2_needed=len(shell_urls),
            tier2_success=tier2_success,
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
                    final_host = resp.url.host if resp.url else ""
                    if self._allowed and not is_allowed_host(final_host or "", self._allowed):
                        return _RedirectRejected(str(resp.url))
                    return resp.text
                if resp.status_code in _RETRY_IN_BROWSER_STATUSES:
                    return _OriginBlocked(resp.status_code)
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

            # Only audio/video is blocked. Aborting images and fonts as well
            # looked like a free bandwidth saving, but Cloudflare's managed
            # challenge needs those assets to complete: with them blocked the
            # challenge never cleared and every protected article came back
            # as the "Just a moment..." page; with them allowed it cleared in
            # about three seconds and returned the real article.
            await context_pw.route(
                "**/*.{mp4,mp3,webm,ogg,avi,mov,m4a}",
                lambda route: route.abort(),
            )

            # Every candidate from a Cloudflare-protected outlet lands here,
            # and each one now waits out a challenge — fetching them one
            # after another put whole verifications into the minutes. Run a
            # few at a time instead; the per-domain courtesy delay in tier 1
            # still applies to the HTTP path.
            semaphore = asyncio.Semaphore(_PLAYWRIGHT_CONCURRENCY)

            async def fetch_one(url: str) -> tuple[str, str | None]:
                async with semaphore:
                    if _host_cooling_down(url):
                        logger.info("s05_host_cooling_down", url=url[:80])
                        return url, None
                    page = await context_pw.new_page()
                    try:
                        await page.goto(
                            url,
                            wait_until="domcontentloaded",
                            timeout=int(_FETCH_TIMEOUT_PLAYWRIGHT * 1000),
                        )

                        await page.wait_for_timeout(1500)
                        final_host = urlparse(page.url).hostname or ""
                        if self._allowed and not is_allowed_host(final_host, self._allowed):
                            return url, _REJECTED
                        html = await page.content()

                        # A Cloudflare interstitial clears itself after a few
                        # seconds; grabbing the DOM too early captures the
                        # "Just a moment..." page instead of the article.
                        if _is_bot_wall(html):
                            for _ in range(_BOT_WALL_RETRIES):
                                await page.wait_for_timeout(_BOT_WALL_WAIT_MS)
                                html = await page.content()
                                if not _is_bot_wall(html):
                                    break
                            else:
                                logger.warning("s05_bot_wall_unresolved", url=url[:80])
                                _mark_walled(url)
                                return url, None

                        logger.debug("s05_playwright_success", url=url[:80])
                        return url, (html if html else None)
                    except Exception as exc:
                        logger.warning(
                            "s05_playwright_failed", url=url[:80], error=str(exc)[:80]
                        )
                        return url, None
                    finally:
                        await page.close()

            for url, html in await asyncio.gather(*(fetch_one(u) for u in urls)):
                results[url] = html

            await context_pw.close()
            await browser.close()

        return results


def _maybe_deamp(candidate):
    url = candidate.url
    if "/amp/" in url or url.endswith("/amp"):
        canonical = re.sub(r"/amp(/|$)", "/", url).rstrip("/")

        return candidate.model_copy(update={"url": canonical})
    return candidate
