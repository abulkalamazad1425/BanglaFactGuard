"""Google News search: one site operator, a date window only where it helps,
and publisher links resolved from Google's redirects. A browser that cannot
run makes the call FAIL (-> INCOMPLETE), never look like an empty search."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.core.exceptions import PyGoogleNewsError
from app.features.search import pygooglenews_client as pgn
from tests.helpers import playwright as fake_playwright

WRAPPED = "https://news.google.com/rss/articles/CBMiabc"
OTHER = "https://news.google.com/rss/articles/CBMixyz"
FINAL = "https://www.prothomalo.com/bangladesh/abc12345"


@pytest.fixture(autouse=True)
def clean_cache():
    pgn._resolved_cache.clear()
    yield
    pgn._resolved_cache.clear()


class FakeGoogleNews:
    def __init__(self, entries=None, error=None):
        self.entries, self.error, self.calls = entries or [], error, []

    def search(self, query, **kwargs):
        self.calls.append((query, kwargs))
        if self.error:
            raise self.error
        return {"entries": self.entries}


def client(monkeypatch, gn: FakeGoogleNews, resolver=None) -> pgn.PyGoogleNewsClient:
    c = pgn.PyGoogleNewsClient()
    c.gn = gn
    if resolver:
        monkeypatch.setattr(c, "_resolve_with_playwright", resolver)
    return c


async def test_query_and_date_window(monkeypatch):
    entries = [{"link": f"https://news.google.com/x?url=https%3A%2F%2Fa.com%2F{i}", "title": f"t{i}"} for i in range(15)]
    gn = FakeGoogleNews(entries + [{"link": "", "title": "no link"}])
    c = client(monkeypatch, gn)
    recent = date.today() - timedelta(days=10)
    results = await c.search_entries("সেতু", domain="prothomalo.com", published_date=recent)
    assert results[0] == ("https://a.com/0", "t0") and len(results) == c.settings.pygooglenews_max_results
    query, window = gn.calls[0]
    assert query == "site:prothomalo.com সেতু" and set(window) == {"from_", "to_"}
    await c.search_entries("site:prothomalo.com সেতু", domain="prothomalo.com", published_date=date(2020, 1, 1))
    assert gn.calls[1] == ("site:prothomalo.com সেতু", {})  # no duplicate operator, no window for old stories
    with pytest.raises(PyGoogleNewsError):
        await client(monkeypatch, FakeGoogleNews(error=RuntimeError("rate limited"))).search_entries("q")
    monkeypatch.setattr(pgn, "_FEED_TIMEOUT_S", 0.1)
    monkeypatch.setattr(gn, "search", lambda *a, **k: __import__("time").sleep(0.5))
    with pytest.raises(PyGoogleNewsError, match="timed out"):  # the feed fetch has no timeout of its own
        await c.search_entries("q")


async def test_redirects_are_resolved_once_and_unresolvable_ones_fail_the_call(monkeypatch):
    calls = []

    async def resolver(urls):
        calls.append(list(urls))
        return {u: FINAL for u in urls if u == WRAPPED}

    gn = FakeGoogleNews([{"link": WRAPPED, "title": "a"}, {"link": WRAPPED, "title": "a"}, {"link": OTHER, "title": "b"}])
    c = client(monkeypatch, gn, resolver)
    assert await c.search_entries("q") == [(FINAL, "a"), (FINAL, "a"), (OTHER, "b")]  # partial resolution is fine
    assert await c.search_entries("q2") == [(FINAL, "a"), (FINAL, "a"), (OTHER, "b")]
    assert calls == [[WRAPPED, OTHER], [OTHER]]  # resolved once, failures never cached

    async def browser_down(urls):
        return {}

    with pytest.raises(PyGoogleNewsError):
        await client(monkeypatch, FakeGoogleNews([{"link": OTHER, "title": "b"}]), browser_down).search_entries("q")


async def test_the_browser_captures_the_publisher_hop_and_a_failed_launch_is_retried(monkeypatch):
    async def no_sleep(_):
        return None

    monkeypatch.setattr(pgn.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(pgn, "_REDIRECT_WAIT_S", 0.2)
    server = "https://news.google.com/rss/articles/server"
    scripts = {
        WRAPPED: {"late": True, "final": FINAL + "?__cf_chl_rt_tk=abc&id=1"},  # the interstitial's JS hop
        server: {"final": FINAL},                             # a 302: aborting it fails goto
        OTHER: {"late": True},                                # never leaves Google
        "https://news.google.com/rss/articles/crash": {"crash": True},
    }
    fake_playwright.install(monkeypatch, scripts)
    resolved = await pgn.PyGoogleNewsClient()._resolve_with_retry(list(scripts))
    assert resolved == {WRAPPED: FINAL + "?id=1", server: FINAL, OTHER: OTHER,
                        "https://news.google.com/rss/articles/crash": "https://news.google.com/rss/articles/crash"}

    # A dead browser never answers: the session deadline returns what was
    # resolved instead of holding the claim at "processing" forever.
    monkeypatch.setattr(pgn, "_SESSION_DEADLINE_S", 0.5)
    hung = "https://news.google.com/rss/articles/hung"
    fake_playwright.install(monkeypatch, {WRAPPED: scripts[WRAPPED], hung: {"hang": True}})
    assert await pgn.PyGoogleNewsClient()._run_playwright_async([WRAPPED, hung]) == {WRAPPED: FINAL + "?id=1"}

    attempts = []
    fake_playwright.install(monkeypatch, scripts, launch_error=OSError("browser would not start"))
    original = pgn.PyGoogleNewsClient._run_playwright_async

    async def counting(self, urls):
        attempts.append(1)
        return await original(self, urls)

    monkeypatch.setattr(pgn.PyGoogleNewsClient, "_run_playwright_async", counting)
    assert await pgn.PyGoogleNewsClient()._resolve_with_retry([WRAPPED]) == {}
    assert len(attempts) == pgn._LAUNCH_ATTEMPTS
    fake_playwright.uninstall(monkeypatch)
    assert await original(pgn.PyGoogleNewsClient(), [WRAPPED]) == {}
