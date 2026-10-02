"""Search failure accounting, date-free retrieval, redirect validation,
publication-date extraction (acceptance 12-15)."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.core.constants import ContentStatus, DateStatus, SearchProvider, SourceStatus
from app.features.search.internal_site_client import InternalSiteSearchError
from app.features.verification.pipeline.stages.s04_source_search import SourceSearchStage
from app.features.verification.pipeline.stages.s05_evidence_retrieval import EvidenceRetrievalStage
from app.features.verification.pipeline.stages.s06_article_extractor import ArticleExtractorStage
from app.features.verification.pipeline.stages.s11_classifier import ClassifierStage
from app.shared.utils.dates import parse_publication
from pipeline_helpers import make_context

URL = "https://www.prothomalo.com/bangladesh/district/abc12345def"


def _client(result=None, exc: Exception | None = None):
    c = MagicMock()
    if exc is not None:
        c.search_entries = AsyncMock(side_effect=exc)
    else:
        c.search_entries = AsyncMock(return_value=result if result is not None else [])
    return c


def _cache():
    cache = MagicMock()
    cache.get_search_result = AsyncMock(return_value=None)
    cache.set_search_result = AsyncMock()
    return cache


def _stage(newsdata, cse, pgn, ddg, internal):
    return SourceSearchStage(newsdata, cse, pgn, ddg, internal, _cache())


def _ctx(published=None):
    ctx = make_context("সরকার নতুন সেতু উদ্বোধন করেছে", published_date=published)
    ctx.search_queries = [
        ("সরকার নতুন সেতু", "keywords"),
        ("সরকার নতুন সেতু উদ্বোধন করেছে", "headline"),
        ("site:prothomalo.com সরকার সেতু", "site_restricted"),
    ]
    ctx.source_config = {"internal_search_url": "https://x/search?q={query}", "article_url_patterns": []}
    ctx.search_attempted = ctx.search_success = ctx.search_success_empty = 0
    ctx.search_adequate = None
    return ctx


# ── 12/13: failure accounting → Incomplete vs Not Found ──────────────────


async def test_all_providers_failing_is_incomplete_not_not_found():
    boom = RuntimeError("provider down")
    stage = _stage(_client(exc=boom), _client(exc=boom), _client(exc=boom), _client(exc=boom), _client(exc=InternalSiteSearchError("down")))
    ctx = await stage.execute(_ctx())

    assert ctx.search_attempted > 0
    assert ctx.search_errors == ctx.search_attempted  # every call counted as failed
    assert ctx.search_success == ctx.search_success_empty == 0
    assert ctx.search_adequate is False
    assert ctx.candidate_urls == []

    ctx = await ClassifierStage().execute(ctx)
    assert ctx.source_status == SourceStatus.INCOMPLETE
    assert ctx.content_status is None and ctx.date_status is None
    assert "could not be completed" in ctx.reasoning


async def test_internal_site_failure_is_not_a_successful_empty_search():
    # previously the client swallowed the error and returned [] -> counted as success
    ok_empty = _client([])
    stage = _stage(ok_empty, ok_empty, ok_empty, ok_empty, _client(exc=InternalSiteSearchError("down")))
    ctx = await stage.execute(_ctx())
    assert ctx.search_provider_outcomes["internal_site"].get("FAILED", 0) >= 1
    assert ctx.search_errors >= 1


async def test_adequate_successful_empty_search_is_not_found():
    empty = _client([])
    stage = _stage(empty, empty, empty, empty, empty)
    ctx = await stage.execute(_ctx())
    assert ctx.search_errors == 0 and ctx.search_success_empty == ctx.search_attempted > 0
    assert ctx.search_adequate is True
    ctx = await ClassifierStage().execute(ctx)
    assert ctx.source_status == SourceStatus.NOT_FOUND
    assert ctx.content_status is None and ctx.date_status is None
    assert ctx.confidence > 0  # negative-check strength = completed share of calls


async def test_mostly_failed_search_is_inadequate_even_if_one_call_returned_empty():
    boom = RuntimeError("x")
    stage = _stage(_client([]), _client(exc=boom), _client(exc=boom), _client(exc=boom), _client(exc=boom))
    ctx = await stage.execute(_ctx())
    assert ctx.search_success_empty >= 1 and ctx.search_errors > ctx.search_success_empty
    assert ctx.search_adequate is False
    assert (await ClassifierStage().execute(ctx)).source_status == SourceStatus.INCOMPLETE


async def test_unconfigured_providers_are_skipped_not_attempted():
    nc = RuntimeError("API key is not configured")
    ok = _client([])
    ctx = _ctx()
    ctx.source_config = {}  # internal search not configured for this outlet
    stage = _stage(_client(exc=nc), _client(exc=nc), ok, ok, ok)
    ctx = await stage.execute(ctx)
    assert ctx.search_skipped > 0
    assert ctx.search_errors == 0
    assert ctx.search_attempted == ctx.search_success_empty


# ── date-free retrieval ─────────────────────────────────────────────────


async def test_claimed_date_is_only_applied_to_date_bound_queries():
    nd, cse, pgn, ddg, internal = (_client([]) for _ in range(5))
    ctx = _ctx(published=date(2026, 6, 7))
    ctx.search_queries = [("সরকার সেতু", "keywords"), ("সরকার সেতু ৭ জুন ২০২৬", "date_bound")]
    await _stage(nd, cse, pgn, ddg, internal).execute(ctx)
    seen = {}
    for client in (nd, cse, pgn, ddg):
        for call in client.search_entries.call_args_list:
            seen.setdefault(call.args[0], set()).add(call.kwargs["published_date"])
    dated = {q for q, d in seen.items() if date(2026, 6, 7) in d}
    undated = {q for q, d in seen.items() if d == {None}}
    assert dated and all("২০২৬" in q for q in dated)  # only the date-bound query carries a date
    assert undated and not (undated & dated)


async def test_off_domain_candidates_are_dropped():
    nd = _client([("https://evil.example/news/a-long-article-1234", "x"), (URL, "ok")])
    empty = _client([])
    ctx = await _stage(nd, empty, empty, empty, empty).execute(_ctx())
    assert [c.url for c in ctx.candidate_urls] == [URL]


# ── redirect validation (S05) ───────────────────────────────────────────

HTML = "<html><body>" + "<p>" + ("খবরের বিস্তারিত " * 60) + "</p></body></html>"


async def test_final_redirected_host_must_belong_to_the_claimed_source():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "www.prothomalo.com":
            return httpx.Response(302, headers={"location": "https://evil.example/landing"})
        if request.url.host == "evil.example":
            return httpx.Response(200, text=HTML)
        return httpx.Response(200, text=HTML)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)
    ctx = make_context("শিরোনাম")
    from app.features.articles.schemas import CandidateArticleSchema

    ctx.candidate_urls = [
        CandidateArticleSchema(url="https://www.prothomalo.com/a/1", search_provider=SearchProvider.DDG, query_type="headline"),
        CandidateArticleSchema(url="https://www.prothomalo.com/ok/2", search_provider=SearchProvider.DDG, query_type="headline"),
    ]

    # first URL redirects away, second serves directly
    async def handler2(request):
        return handler(request)

    def h(request: httpx.Request) -> httpx.Response:
        if request.url.path.startswith("/a/"):
            return httpx.Response(302, headers={"location": "https://evil.example/landing"})
        return httpx.Response(200, text=HTML)

    client = httpx.AsyncClient(transport=httpx.MockTransport(h), follow_redirects=True)
    stage = EvidenceRetrievalStage(client)
    out = await stage.execute(ctx)
    assert list(out._raw_html_cache) == ["https://www.prothomalo.com/ok/2"]
    assert out.search_redirect_rejected == 1
    assert out.fetch_attempted == 1 and out.fetch_errors == 0  # a rejected redirect is not a fetch failure
    await client.aclose()


# ── publication dates (S06 + parser) ────────────────────────────────────


def test_utc_timestamp_converts_to_the_dhaka_calendar_day():
    p = parse_publication("2026-03-15T21:30:00+00:00")
    assert p.local_date == date(2026, 3, 16) and p.tz_assumed is False
    assert p.published_at.utcoffset().total_seconds() == 6 * 3600


def test_offsetless_timestamp_assumes_dhaka_and_says_so():
    p = parse_publication("2026-03-15T21:30:00")
    assert p.local_date == date(2026, 3, 15) and p.tz_assumed is True


def test_date_only_and_bangla_forms():
    assert parse_publication("2026-03-15").local_date == date(2026, 3, 15)
    assert parse_publication("১৫ মার্চ ২০২৬").local_date == date(2026, 3, 15)
    assert parse_publication("not a date") is None


def _html(ld: str = "", meta: str = "", body_cls: str = "story") -> str:
    para = "<p>" + ("এটি একটি দীর্ঘ প্রতিবেদনের অংশ যেখানে বিস্তারিত তথ্য দেওয়া হয়েছে। " * 6) + "</p>"
    return (
        "<html><head><title>সরকার নতুন সেতু উদ্বোধন করেছে</title>"
        f"{meta}{ld}</head><body><h1>সরকার নতুন সেতু উদ্বোধন করেছে</h1>"
        f'<div class="{body_cls}">{para}{para}</div></body></html>'
    )


def _extract(html: str, config=None):
    stage = ArticleExtractorStage(MagicMock())
    return stage._extract_one(URL, html, {}, "prothomalo.com", config)


def test_json_ld_date_published_wins_and_date_modified_is_never_used():
    ld = (
        '<script type="application/ld+json">{"@type":"NewsArticle","headline":"x",'
        '"datePublished":"2026-03-15T21:30:00+00:00","dateModified":"2026-04-01T10:00:00+06:00"}</script>'
    )
    a = _extract(_html(ld=ld))
    assert a.published_date == date(2026, 3, 16)
    assert a.published_date_source == "json_ld.datePublished"
    assert a.published_tz_assumed is False


def test_only_date_modified_means_no_publication_date():
    ld = '<script type="application/ld+json">{"@type":"NewsArticle","dateModified":"2026-04-01T10:00:00+06:00"}</script>'
    meta = '<meta property="article:modified_time" content="2026-04-01T10:00:00+06:00">'
    a = _extract(_html(ld=ld, meta=meta))
    assert a.published_date is None and a.published_date_source is None


def test_meta_published_time_and_graph_json_ld():
    a = _extract(_html(meta='<meta property="article:published_time" content="2026-03-15T08:00:00+06:00">'))
    assert a.published_date == date(2026, 3, 15) and a.published_date_source == "meta.article:published_time"
    ld = '<script type="application/ld+json">{"@graph":[{"@type":"WebSite"},{"@type":"NewsArticle","datePublished":"2026-05-02"}]}</script>'
    assert _extract(_html(ld=ld)).published_date == date(2026, 5, 2)


def test_selector_based_extraction_still_finds_the_publication_date():
    # title+body come from the outlet's selectors (early-return path); the
    # date must still be found rather than silently missing.
    cfg = {"title_selectors": ["h1"], "body_selectors": ["div.story"], "date_selectors": []}
    ld = '<script type="application/ld+json">{"@type":"NewsArticle","datePublished":"2026-03-15T08:00:00+06:00"}</script>'
    a = _extract(_html(ld=ld), cfg)
    assert a.published_date == date(2026, 3, 15)
    assert a.extraction_method.value == "source_specific"


# ── 14/15 at the classifier: date independent of content ────────────────


async def test_missing_article_date_is_incomplete_and_independent_of_content():
    from pipeline_helpers import article, run_analysis

    t = "সরকার নতুন সেতু উদ্বোধন করেছে"
    ctx = make_context(t, published_date=date(2026, 3, 15), top=article(t, t + "।", published=None))
    ctx = await run_analysis(ctx)
    assert ctx.content_status == ContentStatus.MATCHED
    assert ctx.date_status == DateStatus.INCOMPLETE
