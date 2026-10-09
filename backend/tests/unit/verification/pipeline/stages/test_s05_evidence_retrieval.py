"""S05: fetch candidate pages from the claimed source only. Anti-bot blocks
go to the browser tier; a redirect off the source is a rejected candidate,
never a fetch failure."""

from __future__ import annotations

import httpx
import pytest

from app.core.constants import SearchProvider
from app.features.articles.schemas import CandidateArticleSchema
from app.features.verification import source_policy
from app.features.verification.pipeline.stages import s05_evidence_retrieval as s05
from tests.helpers import playwright as fake_playwright
from tests.helpers.pipeline import make_context

ARTICLE = "<html><body><p>" + "খবরের বিস্তারিত " * 200 + "</p></body></html>"
BOT_WALL = "<html><title>Just a moment...</title><script>" + "x" * 5000 + "</script></html>"
BASE = "https://www.prothomalo.com"


@pytest.fixture(autouse=True)
def no_delays(monkeypatch):
    async def instant(_):
        return None

    monkeypatch.setattr(s05.asyncio, "sleep", instant)
    monkeypatch.setattr(s05, "_walled_until", {})


def candidates(*paths: str) -> list[CandidateArticleSchema]:
    return [
        CandidateArticleSchema(url=p if p.startswith("http") else BASE + p,
                               search_provider=SearchProvider.PY_GOOGLE_NEWS, query_type="headline")
        for p in paths
    ]


def client(routes: dict) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        action = routes.get(request.url.path, 404)
        if isinstance(action, Exception):
            raise action
        if isinstance(action, str) and action.startswith("http"):
            return httpx.Response(302, headers={"location": action})
        if isinstance(action, str):
            return httpx.Response(200, text=action)
        return httpx.Response(action)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)


def context(*paths):
    ctx = make_context("শিরোনাম")
    ctx.candidate_urls = candidates(*paths)
    return ctx


async def test_tiers_failures_and_off_source_redirects_are_kept_apart(monkeypatch):
    routes = {"/ok": ARTICLE, "/blocked": 403, "/wall": BOT_WALL, "/dead": 404, "/down": httpx.ConnectError("x"),
              "/away": "https://evil.example/landing", "/landing": ARTICLE}
    browser_calls = []

    async def browser(self, urls):
        browser_calls.append(urls)
        return {BASE + "/blocked": ARTICLE, BASE + "/wall": s05._REJECTED}

    monkeypatch.setattr(s05.EvidenceRetrievalStage, "_fetch_playwright_batch", browser)
    async with client(routes) as http:
        out = await s05.EvidenceRetrievalStage(http).execute(context("/ok", "/blocked", "/wall", "/dead", "/down", "/away"))
    assert browser_calls == [[BASE + "/blocked", BASE + "/wall"]]
    assert set(out.fetched_html) == {BASE + "/ok", BASE + "/blocked"}
    assert out.search_redirect_rejected == 2
    assert sorted(out.failed_extraction_urls) == [BASE + "/dead", BASE + "/down"]
    assert (out.fetch_attempted, out.fetch_errors) == (4, 2)


async def test_candidates_are_cleaned_capped_and_restricted_to_the_allowed_scope(monkeypatch):
    monkeypatch.setattr(s05._SETTINGS.search, "top_k_candidates", 2)
    requested = []
    async with client({}) as http:
        http.get = lambda url, **kw: requested.append(url) or _response(url)
        await s05.EvidenceRetrievalStage(http).execute(
            context("https://www.google.com/search?q=x", "/story/amp", "/b", "/c")
        )
    assert requested == [BASE + "/story", BASE + "/b"]  # search page dropped, AMP undone, capped at 2

    verified = context("https://www.jugantor.com/a/1", "https://www.unknown.com/a/1")
    verified.verification_mode = source_policy.VERIFIED_SOURCES
    verified.verified_scope = source_policy.VerifiedScope([source_policy.VerifiedPublisher("jugantor.com", "j", ["jugantor.com"], {})])
    requested.clear()
    async with client({}) as http:
        http.get = lambda url, **kw: requested.append(url) or _response(url)
        await s05.EvidenceRetrievalStage(http).execute(verified)
        verified.verified_scope = source_policy.VerifiedScope()
        assert (await s05.EvidenceRetrievalStage(http).execute(verified)).fetched_html == {}
    assert requested == ["https://www.jugantor.com/a/1"]


async def _response(url):
    return httpx.Response(200, text=ARTICLE, request=httpx.Request("GET", url))


# ── browser tier (fake Playwright) ───────────────────────────────────────

async def test_browser_waits_out_challenges_and_backs_off_from_walled_hosts(monkeypatch):
    walled_url, cooling_url = "https://walled.example/a/1", "https://walled.example/a/2"
    scripts = {
        BASE + "/cleared": {"contents": [BOT_WALL, ARTICLE]},
        walled_url: {"contents": [BOT_WALL]},
        BASE + "/moved": {"contents": [ARTICLE], "final": "https://evil.example/x"},
        BASE + "/crash": {"crash": True},
    }
    opened = fake_playwright.install(monkeypatch, scripts)
    stage = s05.EvidenceRetrievalStage(httpx.AsyncClient())
    stage._allowed = ["prothomalo.com", "walled.example"]
    results = await stage._run_playwright_async(list(scripts))
    assert results == {BASE + "/cleared": ARTICLE, walled_url: None, BASE + "/moved": s05._REJECTED, BASE + "/crash": None}
    # the walled host is now left alone: its next page is not even opened
    assert s05._host_cooling_down(cooling_url)
    opened.clear()
    assert await stage._run_playwright_async([cooling_url]) == {cooling_url: None} and opened == []


async def test_without_playwright_installed_browser_pages_are_failures(monkeypatch):
    fake_playwright.uninstall(monkeypatch)
    stage = s05.EvidenceRetrievalStage(httpx.AsyncClient())
    assert await stage._run_playwright_async(["https://a/1"]) == {"https://a/1": None}


def test_cooldown_expires(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(s05.time, "monotonic", lambda: now[0])
    url = "https://bangla.thedailystar.net/news/1"
    assert not s05._host_cooling_down(url)
    s05._mark_walled(url)
    assert s05._host_cooling_down("https://bangla.thedailystar.net/news/2")
    assert not s05._host_cooling_down("https://samakal.com/bangladesh/article/1")
    now[0] += s05._WALL_COOLDOWN_S + 1
    assert not s05._host_cooling_down(url)


def test_interstitials_need_both_a_marker_and_almost_no_text():
    assert s05._is_bot_wall(BOT_WALL)
    assert not s05._is_bot_wall(ARTICLE.replace("<body>", "<body>challenge-platform"))
    assert s05._is_shell_html('<div id="root"></div><script>' + "x" * 9000 + "</script>")
    assert not s05._is_shell_html(ARTICLE)
