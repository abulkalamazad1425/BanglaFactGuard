"""S04: per-call outcome accounting (a failed search is never an empty one),
domain restriction, de-duplication and the verified-sources search."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

from app.core.constants import SearchProvider
from app.features.verification import source_policy
from app.features.verification.pipeline.stages.s04_source_search import (
    SourceSearchStage,
    _cached_entries,
    _canonicalise_url,
    _title_relevance,
)
from tests.helpers.pipeline import make_context

HEADLINE = "সরকার নতুন সেতু উদ্বোধন করেছে"
URL = "https://www.prothomalo.com/bangladesh/district/abc12345def"
INTERNAL = {"internal_search_url": "https://www.prothomalo.com/search?q={query}", "article_url_patterns": []}


def provider(entries=None, exc: Exception | None = None) -> MagicMock:
    return MagicMock(search_entries=AsyncMock(side_effect=exc, return_value=list(entries or [])))


def cache(cached: dict | None = None) -> MagicMock:
    return MagicMock(get_search_result=AsyncMock(side_effect=lambda p, h: (cached or {}).get(p)),
                     set_search_result=AsyncMock())


def ctx(published=None, *, config=INTERNAL, source="prothomalo.com"):
    c = make_context(HEADLINE, published_date=published)
    c.normalized_source, c.source_config = source, config
    c.search_queries = [(f"site:{source} সরকার নতুন সেতু", "keywords"), (f"site:{source} {HEADLINE}", "headline")]
    c.search_attempted = c.search_success = c.search_success_empty = 0
    c.search_adequate = None
    return c


async def search(context, google, internal, c=None):
    return await SourceSearchStage(google, internal, c or cache()).execute(context)


async def test_all_providers_failing_is_an_inadequate_search_not_an_empty_one():
    out = await search(ctx(), provider(exc=RuntimeError("down")), provider(exc=RuntimeError("down")))
    assert out.search_attempted == out.search_errors == 4 and out.search_adequate is False
    assert out.search_provider_outcomes["internal_site"]["FAILED"] == 2 and out.stage_errors


async def test_an_adequate_empty_search_and_an_unconfigured_outlet_search():
    out = await search(ctx(), provider([]), provider([]))
    assert out.search_attempted == out.search_success_empty == 4 and out.search_adequate is True
    internal = provider([])
    out = await search(ctx(config={}), provider([]), internal)
    internal.search_entries.assert_not_called()
    assert (out.search_skipped, out.search_attempted, out.search_adequate) == (2, 2, True)
    not_configured = await search(ctx(), provider([]), provider(exc=RuntimeError("Search not configured")))
    assert not_configured.search_skipped == 2


async def test_both_providers_get_every_keyword_and_only_date_bound_queries_get_the_date():
    google, internal = provider([]), provider([])
    c = ctx(date(2026, 10, 4))
    keywords = "one two three four five six seven eight"
    c.search_queries = [(f"site:prothomalo.com {keywords}", "keywords"),
                        (f"site:prothomalo.com {keywords} 04 October 2026", "date_bound")]
    await search(c, google, internal)
    for client in (google, internal):
        first, second = client.search_entries.call_args_list
        assert keywords in first.args[0] and first.kwargs["published_date"] is None
        assert second.kwargs["published_date"] == date(2026, 10, 4)
        assert first.kwargs["domain"] == "prothomalo.com"
    assert google.search_entries.call_args_list[0].args[0].startswith("site:prothomalo.com ")
    assert not internal.search_entries.call_args_list[0].args[0].startswith("site:")  # the outlet's own search


async def test_candidates_are_on_domain_articles_deduplicated_and_cached():
    google = provider([
        ("https://evil.example/news/a-long-article-1234", "x"),        # off domain
        ("https://www.prothomalo.com/tag/dhaka", "x"),                  # not an article
        (URL + "?utm_source=fb", "t"), (URL + "/amp", "t"),             # same article twice
    ])
    internal = provider([(URL, "t")])
    c = cache()
    out = await search(ctx(), google, internal, c)
    assert [x.url for x in out.candidate_urls] == [URL]
    assert out.candidate_urls[0].search_provider == SearchProvider.INTERNAL_SITE  # outlet's own result preferred
    assert c.set_search_result.await_count == 4


async def test_cached_results_are_served_without_calling_the_provider():
    google = provider()
    c = cache({"py_google_news": [[URL, "শিরোনাম"]], "internal_site": [URL]})
    out = await search(ctx(), google, provider(), c)
    google.search_entries.assert_not_called()
    assert out.search_cached == 4 and out.search_adequate and out.candidate_urls[0].url == URL


async def test_missing_queries_or_source_dispatch_nothing():
    google = provider()
    no_queries = ctx()
    no_queries.search_queries = []
    for c in (ctx(source=None), no_queries):  # never an unrestricted search
        out = await search(c, google, provider())
        assert out.stage_errors and out.candidate_urls == []
    google.search_entries.assert_not_called()


def verified(*publishers: str):
    c = ctx(source=None, config=None)
    c.verification_mode = source_policy.VERIFIED_SOURCES
    c.verified_scope = source_policy.VerifiedScope(
        [source_policy.VerifiedPublisher(p, p, [p], {"article_url_patterns": []}) for p in publishers]
    )
    c.search_queries = [(HEADLINE, "headline")]
    return c


async def test_verified_sources_search_is_google_only_grouped_and_allowlisted(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings().search, "fallback_domain_group_size", 2)
    google = provider([
        ("https://www.jugantor.com.evil.net/national/123456", HEADLINE),   # deceptive host
        ("https://www.unknown-news.com/national/123456", HEADLINE),       # off the list
        ("https://www.samakal.com/national/999999", "চট্টগ্রাম বন্দরে জাহাজ ভিড়েছে - সমকাল"),  # irrelevant
        ("https://www.samakal.com/national/888888", None),                 # untitled: kept, last
        ("https://www.jugantor.com/national/123456", f"{HEADLINE} - যুগান্তর"),
    ])
    internal = provider()
    out = await search(verified("jugantor.com", "prothomalo.com", "samakal.com"), google, internal)
    internal.search_entries.assert_not_called()
    queries = [call.args[0] for call in google.search_entries.call_args_list]
    assert queries == [f"site:jugantor.com OR site:prothomalo.com {HEADLINE}", f"site:samakal.com {HEADLINE}"]
    assert [c.url for c in out.candidate_urls] == [
        "https://www.jugantor.com/national/123456", "https://www.samakal.com/national/888888",
    ]
    empty = verified()
    assert (await search(empty, google, internal)).stage_errors


def test_url_canonicalisation_and_helpers():
    assert _canonicalise_url("http://WWW.A.com/x/amp/?utm_source=1&id=2&__cf_chl=z") == "https://www.a.com/x?id=2"
    assert _title_relevance(HEADLINE, f"{HEADLINE} - নয়া দিগন্ত") == 1.0
    assert _title_relevance(HEADLINE, "চট্টগ্রাম বন্দরে জাহাজ ভিড়েছে - সমকাল") == 0.0
    assert _title_relevance(HEADLINE, None) is None
    assert _cached_entries([["https://a/1", "t"], "https://a/2", ["https://a/3", None], 5]) == [
        ("https://a/1", "t"), ("https://a/2", None), ("https://a/3", None),
    ]
