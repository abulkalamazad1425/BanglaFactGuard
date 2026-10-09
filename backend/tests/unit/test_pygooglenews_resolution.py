"""Google News link resolution: a browser that cannot start must make the
call FAIL (-> INCOMPLETE), never look like an empty search (-> NOT_FOUND);
a launch failure is retried; a resolved link is not resolved twice."""

import pytest

from app.core.exceptions import PyGoogleNewsError
from app.features.search import pygooglenews_client as pgn

WRAPPED = "https://news.google.com/rss/articles/CBMiabc"
FINAL = "https://www.prothomalo.com/bangladesh/abc12345"


@pytest.fixture(autouse=True)
def clean_cache():
    pgn._resolved_cache.clear()
    yield
    pgn._resolved_cache.clear()


def client(monkeypatch, entries, resolver):
    c = pgn.PyGoogleNewsClient()
    monkeypatch.setattr(c, "_sync_search", lambda q, d, p: list(entries))
    monkeypatch.setattr(c, "_resolve_with_playwright", resolver)
    return c


async def test_unresolvable_links_fail_the_call(monkeypatch):
    async def browser_down(urls):
        return {}

    c = client(monkeypatch, [(WRAPPED, "t")], browser_down)
    with pytest.raises(PyGoogleNewsError):
        await c.search_entries("q")


async def test_resolved_links_are_cached(monkeypatch):
    calls = []

    async def resolver(urls):
        calls.append(list(urls))
        return {u: FINAL for u in urls}

    c = client(monkeypatch, [(WRAPPED, "t"), (WRAPPED, "t")], resolver)
    assert await c.search_entries("q") == [(FINAL, "t"), (FINAL, "t")]
    assert await c.search_entries("q2") == [(FINAL, "t"), (FINAL, "t")]
    assert calls == [[WRAPPED]]  # resolved once, deduplicated


async def test_launch_failure_is_retried(monkeypatch):
    attempts = []

    async def flaky(self, urls):
        attempts.append(1)
        return {} if len(attempts) == 1 else {u: FINAL for u in urls}

    async def no_sleep(_):
        return None

    monkeypatch.setattr(pgn.PyGoogleNewsClient, "_run_playwright_async", flaky)
    monkeypatch.setattr(pgn.asyncio, "sleep", no_sleep)
    c = pgn.PyGoogleNewsClient()
    assert await c._resolve_with_retry([WRAPPED]) == {WRAPPED: FINAL}
    assert len(attempts) == 2


async def test_partial_resolution_still_succeeds(monkeypatch):
    async def resolver(urls):
        return {urls[0]: FINAL}

    other = "https://news.google.com/rss/articles/CBMixyz"
    c = client(monkeypatch, [(WRAPPED, "a"), (other, "b")], resolver)
    assert await c.search_entries("q") == [(FINAL, "a"), (other, "b")]
