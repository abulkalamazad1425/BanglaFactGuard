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
from app.features.verification.pipeline.stages.s08_source_correspondence import SourceCorrespondenceStage
from app.shared.utils.dates import parse_publication
from pipeline_helpers import FakeEmbedder, make_context

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


def _stage(pgn, internal):
    return SourceSearchStage(pgn, internal, _cache())


def _ctx(published=None):
    ctx = make_context("সরকার নতুন সেতু উদ্বোধন করেছে", published_date=published)
    ctx.search_queries = [
        ("site:prothomalo.com সরকার নতুন সেতু", "keywords"),
        ("site:prothomalo.com সরকার নতুন সেতু উদ্বোধন করেছে", "headline"),
    ]
    ctx.source_config = {"internal_search_url": "https://www.prothomalo.com/search?q={query}", "article_url_patterns": []}
    ctx.search_attempted = ctx.search_success = ctx.search_success_empty = 0
    ctx.search_adequate = None
    return ctx


async def test_all_providers_failing_is_incomplete_not_not_found():
    ctx = await _stage(_client(exc=RuntimeError("down")), _client(exc=InternalSiteSearchError("down"))).execute(_ctx())
    assert ctx.search_attempted == ctx.search_errors == 4
    assert ctx.search_adequate is False
    assert (await SourceCorrespondenceStage(FakeEmbedder()).execute(ctx)).source_status == SourceStatus.INCOMPLETE


async def test_internal_site_failure_is_not_successful_empty_search():
    ctx = await _stage(_client([]), _client(exc=InternalSiteSearchError("down"))).execute(_ctx())
    assert ctx.search_provider_outcomes["internal_site"]["FAILED"] == 2
    assert ctx.search_errors == 2


async def test_adequate_empty_search_is_not_found():
    ctx = await _stage(_client([]), _client([])).execute(_ctx())
    assert ctx.search_attempted == ctx.search_success_empty == 4
    assert ctx.search_adequate is True
    assert (await SourceCorrespondenceStage(FakeEmbedder()).execute(ctx)).source_status == SourceStatus.NOT_FOUND


async def test_unconfigured_internal_search_is_skipped():
    ctx = _ctx()
    ctx.source_config = {}
    internal = _client([])
    ctx = await _stage(_client([]), internal).execute(ctx)
    internal.search_entries.assert_not_called()
    assert ctx.search_skipped == 2
    assert ctx.search_attempted == ctx.search_success_empty == 2
    assert ctx.search_adequate is True


@pytest.mark.parametrize("domain", ["prothomalo.com", "bd-pratidin.com", "ittefaq.com.bd", "jugantor.com", "bangla.thedailystar.net"])
async def test_internal_search_and_google_both_run_for_every_source(domain):
    ctx = _ctx()
    ctx.normalized_source = domain
    ctx.source_config = {"internal_search_url": f"https://www.{domain}/search?q={{query}}", "article_url_patterns": []}
    internal, pgn = _client([]), _client([])
    await _stage(pgn, internal).execute(ctx)
    assert internal.search_entries.await_count == 2
    assert pgn.search_entries.await_count == 2


async def test_date_variants_and_all_keywords_reach_only_retained_providers():
    pgn, internal = _client([]), _client([])
    ctx = _ctx(date(2026, 10, 4))
    keywords = "one two three four five six seven eight"
    ctx.search_queries = [(f"site:prothomalo.com {keywords}", "keywords"),
                          (f"site:prothomalo.com {keywords} 04 October 2026", "date_bound")]
    ctx = await _stage(pgn, internal).execute(ctx)
    assert set(ctx.search_provider_outcomes) == {"internal_site", "py_google_news"}
    for client in (pgn, internal):
        calls = client.search_entries.call_args_list
        assert len(calls) == 2
        assert keywords in calls[0].args[0]
        assert calls[0].kwargs["published_date"] is None
        assert calls[1].kwargs["published_date"] == date(2026, 10, 4)
        assert all(c.kwargs["domain"] == "prothomalo.com" for c in calls)
    assert all(c.args[0].startswith("site:prothomalo.com ") for c in pgn.search_entries.call_args_list)


async def test_missing_source_never_dispatches_search():
    ctx = _ctx()
    ctx.normalized_source = None
    pgn, internal = _client(), _client()
    ctx = await _stage(pgn, internal).execute(ctx)
    pgn.search_entries.assert_not_called()
    internal.search_entries.assert_not_called()
    assert ctx.stage_errors


async def test_off_domain_candidates_are_dropped():
    pgn = _client([("https://evil.example/news/a-long-article-1234", "x"), (URL, "ok")])
    ctx = await _stage(pgn, _client([])).execute(_ctx())
    assert [c.url for c in ctx.candidate_urls] == [URL]


async def test_internal_client_preserves_full_query():
    from app.features.search.internal_site_client import InternalSiteSearchClient
    captured = []
    def handler(request):
        captured.append(request.url.params["q"])
        return httpx.Response(200, text="<html></html>")
    query = "one two three four five six seven eight R&D #report"
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        await InternalSiteSearchClient(http).search_entries(query, domain="prothomalo.com",
            source_config={"internal_search_url": "https://prothomalo.com/search?q={query}"})
    assert captured == [query]


async def test_internal_client_searches_any_configured_source():
    from app.features.search.internal_site_client import InternalSiteSearchClient
    requested = []
    def handler(request):
        requested.append(str(request.url))
        return httpx.Response(200, text="<html></html>")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        await InternalSiteSearchClient(http).search_entries(
            "যুগান্তর কিছু খবর", domain="jugantor.com",
            source_config={"internal_search_url": "https://www.jugantor.com/search?q={query}"},
        )
    assert requested and requested[0].startswith("https://www.jugantor.com/search")


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
    assert list(out.fetched_html) == ["https://www.prothomalo.com/ok/2"]
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


# ── date verification is independent of the headline verdict ────────────


async def test_missing_article_date_is_incomplete_and_independent_of_content():
    from pipeline_helpers import article, run_analysis

    t = "সরকার নতুন সেতু উদ্বোধন করেছে"
    ctx = make_context(t, published_date=date(2026, 3, 15), top=article(t, t + "।", published=None))
    ctx = await run_analysis(ctx)
    assert ctx.content_status == ContentStatus.MATCHED
    assert ctx.date_status == DateStatus.INCOMPLETE
