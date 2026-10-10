from __future__ import annotations

import asyncio
import contextlib
import re
import threading
from collections import OrderedDict
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
_REDIRECT_WAIT_S = 12.0

# A crashed Chromium can leave a Playwright call waiting forever. Nothing
# else bounds this stage and the job heartbeat keeps the claim RUNNING, so it
# would sit at "processing" for good: cap one browser session, and each
# cleanup step, then hand back whatever was resolved.
_SESSION_DEADLINE_S = 60.0
_CLEANUP_TIMEOUT_S = 5.0
# pygooglenews fetches the feed with no timeout of its own.
_FEED_TIMEOUT_S = 30.0

# Hosts the interstitial itself needs. Any other request is the publisher (or
# a tracker): it is never loaded - its URL is all we want.
_GOOGLE_HOST_RE = re.compile(
    r"(^|\.)(google\.com|gstatic\.com|googleapis\.com|googleusercontent\.com)$"
)

# Date-bounded Google News queries only behave on reasonably fresh stories.
# Past this age the feed answers a bounded query with a near-empty set even
# when the unbounded one returns the article — a claim dated Feb 2025 went
# from ten results to one, losing the article being verified. Older claims
# are better served by an unbounded query, with the date used for ranking.
_DATE_FILTER_MAX_AGE = timedelta(days=180)


# Every search call resolves its news.google.com links in a headless browser,
# and the calls of one claim run in parallel (on Windows each in its own
# thread and event loop). Six matches the most a single claim has always used
# (six phrasings), so a normal check is never slowed down; the cap only stops
# overlapping checks from piling up more browsers than the machine can start.
# A launch that still fails is retried once (see _resolve_with_retry).
_MAX_CONCURRENT_BROWSERS = 6
_BROWSER_SLOTS = threading.BoundedSemaphore(_MAX_CONCURRENT_BROWSERS)
_LAUNCH_ATTEMPTS = 2

# The same Google link comes back from several phrasings of one claim (and
# from re-checks): resolve it once. Bounded, process-wide.
_RESOLVED_CACHE_MAX = 2000
_resolved_cache: "OrderedDict[str, str]" = OrderedDict()
_resolved_lock = threading.Lock()


def _cached_resolution(url: str) -> str | None:
    with _resolved_lock:
        final = _resolved_cache.get(url)
        if final is not None:
            _resolved_cache.move_to_end(url)
        return final


def _remember_resolution(url: str, final: str) -> None:
    if "news.google.com" in final:
        return  # unresolved: never cache a failure
    with _resolved_lock:
        _resolved_cache[url] = final
        _resolved_cache.move_to_end(url)
        while len(_resolved_cache) > _RESOLVED_CACHE_MAX:
            _resolved_cache.popitem(last=False)


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
        try:
            entries = await asyncio.wait_for(
                asyncio.to_thread(self._sync_search, query, domain, published_date),
                _FEED_TIMEOUT_S,
            )
        except TimeoutError as exc:
            raise PyGoogleNewsError("Google News feed timed out") from exc

        wrapped_urls = [u for u, _ in entries if "news.google.com" in u]
        if wrapped_urls:
            resolved_map = {u: f for u in wrapped_urls if (f := _cached_resolution(u))}
            pending = [u for u in dict.fromkeys(wrapped_urls) if u not in resolved_map]
            if pending:
                fresh = await self._resolve_with_playwright(pending)
                for orig, final in fresh.items():
                    _remember_resolution(orig, final)
                resolved_map.update(fresh)
            final_entries = [(resolved_map.get(url, url), title) for url, title in entries]
            if not any("news.google.com" not in u for u, _ in final_entries):
                # Every link is still a Google redirect (the browser could not
                # run): the publisher URLs are unknown, so this call FAILED. It
                # must not look like a search that ran and found nothing.
                raise PyGoogleNewsError("Google News links could not be resolved to article URLs")
            return final_entries

        return entries

    async def _resolve_with_playwright(self, urls: list[str]) -> dict[str, str]:
        import sys

        if sys.platform == "win32":
            return await asyncio.to_thread(self._run_playwright_sync, urls)
        # Non-Windows: wait for a browser slot without blocking the event loop.
        await asyncio.to_thread(_BROWSER_SLOTS.acquire)
        try:
            return await self._resolve_with_retry(urls)
        finally:
            _BROWSER_SLOTS.release()

    async def _resolve_with_retry(self, urls: list[str]) -> dict[str, str]:
        resolved: dict[str, str] = {}
        for attempt in range(_LAUNCH_ATTEMPTS):
            resolved = await self._run_playwright_async(urls)
            if resolved:
                return resolved
            if attempt + 1 < _LAUNCH_ATTEMPTS:
                logger.warning("pgn_browser_retry", attempt=attempt + 1)
                await asyncio.sleep(1.5)
        return resolved

    def _run_playwright_sync(self, urls: list[str]) -> dict[str, str]:
        import asyncio
        import sys

        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        _BROWSER_SLOTS.acquire()
        try:
            return loop.run_until_complete(self._resolve_with_retry(urls))
        finally:
            _BROWSER_SLOTS.release()
            loop.close()

    async def _run_playwright_async(self, urls: list[str]) -> dict[str, str]:
        resolved: dict[str, str] = {}
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.warning("pygooglenews_playwright_not_installed")
            return {}

        try:
            pw = await asyncio.wait_for(async_playwright().start(), _CLEANUP_TIMEOUT_S * 4)
        except Exception as exc:
            logger.error("pgn_playwright_error", error=str(exc))
            return {}

        work = asyncio.ensure_future(self._resolve_in_browser(pw, urls, resolved))
        done, _ = await asyncio.wait({work}, timeout=_SESSION_DEADLINE_S)
        if not done:
            logger.warning(
                "pgn_resolve_deadline", resolved=len(resolved), total=len(urls)
            )
            work.cancel()
        # Stopping the driver closes its browser and fails every call still
        # waiting on it, so a hung page cannot outlive this session.
        try:
            await asyncio.wait_for(pw.stop(), _CLEANUP_TIMEOUT_S)
        except Exception as exc:
            logger.warning("pgn_playwright_stop_failed", error=str(exc)[:120])
        await asyncio.wait({work}, timeout=_CLEANUP_TIMEOUT_S)
        if work.done() and not work.cancelled() and work.exception():
            logger.error("pgn_playwright_error", error=str(work.exception()))
        return dict(resolved)

    async def _resolve_in_browser(
        self, pw, urls: list[str], resolved: dict[str, str]
    ) -> None:
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
        landing: dict = {}  # page -> future of the publisher URL it heads to

        # Google News hands back an interstitial that redirects to the
        # publisher from JS. Only that hop's URL is needed: the publisher page
        # is never loaded. Loading it (ads, sign-in and push scripts on every
        # tab of six parallel browsers) exhausted memory and crashed Chromium.
        async def route_request(route) -> None:
            request = route.request
            host = (urlparse(request.url).hostname or "").lower()
            google = bool(_GOOGLE_HOST_RE.search(host))
            allowed = google and request.resource_type not in ("image", "font", "media")
            if not google:
                # e.g. a service-worker request has no frame
                with contextlib.suppress(Exception):
                    if request.is_navigation_request():
                        page = request.frame.page
                        hop = landing.get(page)
                        if hop and not hop.done() and request.frame == page.main_frame:
                            hop.set_result(request.url)
            # the page may close while the request is in flight
            with contextlib.suppress(Exception):
                await (route.continue_() if allowed else route.abort())

        await context.route("**/*", route_request)

        # Resolving several redirect pages at once on one browser context
        # causes enough contention that some hops come late even though a
        # single page resolves in ~2-3s - cap concurrency.
        semaphore = asyncio.Semaphore(4)

        async def resolve_one(url: str) -> None:
            async with semaphore:
                page = await context.new_page()
                hop = asyncio.get_running_loop().create_future()
                landing[page] = hop
                try:
                    await page.goto(url, wait_until="commit", timeout=20000)
                    # A fixed pause races the redirect - when it loses, the
                    # unresolved news.google.com URL flows on to S04, where
                    # the domain filter silently drops it and the real
                    # article is lost. Wait for the hop.
                    try:
                        final_url = await asyncio.wait_for(hop, _REDIRECT_WAIT_S)
                    except TimeoutError:
                        final_url = url
                        logger.warning("pgn_resolve_incomplete", url=url[:60])
                    final_url = _strip_challenge_params(final_url)
                    logger.debug("pgn_resolved_url", orig=url[:60], final=final_url[:60])
                    resolved[url] = final_url
                except Exception as exc:
                    if hop.done() and not hop.cancelled():
                        # A server-side redirect: the aborted hop failed goto
                        # itself, but its URL was already captured.
                        resolved[url] = _strip_challenge_params(hop.result())
                    else:
                        logger.warning("pgn_resolve_failed", url=url[:60], error=str(exc))
                        resolved[url] = url
                finally:
                    landing.pop(page, None)
                    with contextlib.suppress(Exception):
                        await asyncio.wait_for(page.close(), _CLEANUP_TIMEOUT_S)

        await asyncio.gather(*(resolve_one(u) for u in urls))
        with contextlib.suppress(Exception):
            await asyncio.wait_for(browser.close(), _CLEANUP_TIMEOUT_S)
