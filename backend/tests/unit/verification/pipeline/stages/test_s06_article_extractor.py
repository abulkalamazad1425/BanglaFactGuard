"""S06: title, body and datePublished from fetched pages, with provenance.
dateModified and crawl dates are never a publication date."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest
from bs4 import BeautifulSoup

from app.core.constants import ExtractionMethod, SearchProvider
from app.features.articles.schemas import CandidateArticleSchema
from app.features.verification import source_policy
from app.features.verification.pipeline.stages import s06_article_extractor as s06
from app.features.verification.pipeline.stages.s06_article_extractor import (
    ArticleExtractorStage,
    _headline_variants,
)
from tests.helpers.pipeline import make_context

URL = "https://www.prothomalo.com/bangladesh/district/abc12345def"
TITLE = "সরকার নতুন সেতু উদ্বোধন করেছে"
PARA = "<p>" + ("এটি একটি দীর্ঘ প্রতিবেদনের অংশ যেখানে বিস্তারিত তথ্য দেওয়া হয়েছে। " * 6) + "</p>"


def page(head: str = "", body: str = f'<h1>{TITLE}</h1><div class="story">{PARA}{PARA}</div>') -> str:
    return f"<html><head><title>{TITLE} | প্রথম আলো</title>{head}</head><body>{body}</body></html>"


def ld(payload: str) -> str:
    return f'<script type="application/ld+json">{payload}</script>'


def extract(html: str, config=None, candidate=None):
    return ArticleExtractorStage(MagicMock())._extract_one(
        URL, html, {URL: candidate} if candidate else {}, "prothomalo.com", config
    )


@pytest.mark.parametrize("head,expected,source", [
    (ld('{"@type":"NewsArticle","datePublished":"2026-03-15T21:30:00+00:00","dateModified":"2026-04-01T10:00:00+06:00"}'),
     date(2026, 3, 16), "json_ld.datePublished"),                                        # Dhaka day, not modified
    (ld('{"@graph":[{"@type":"WebSite"},{"@type":"NewsArticle","datePublished":"2026-05-02"}]}'),
     date(2026, 5, 2), "json_ld.datePublished"),
    ('<meta property="article:published_time" content="2026-03-15T08:00:00+06:00">',
     date(2026, 3, 15), "meta.article:published_time"),
    ('<meta property="article:modified_time" content="2026-04-01T10:00:00+06:00">' + ld('{"dateModified":"2026-04-01"}'),
     None, None),                                                                       # only a modification date
])
def test_publication_date_and_provenance(head, expected, source):
    a = extract(page(head))
    assert (a.published_date, a.published_date_source) == (expected, source)


def test_outlet_selectors_give_title_body_and_date():
    cfg = {"title_selectors": ["h1"], "body_selectors": ["div.story"], "date_selectors": ["span.when"]}
    a = extract(page(body=f'<h1>{TITLE}</h1><span class="when">২০২৬-০৩-১৫</span><div class="story">{PARA}{PARA}</div>'), cfg)
    assert a.extraction_method == ExtractionMethod.SOURCE_SPECIFIC and a.title == TITLE and a.has_body
    assert (a.published_date, a.published_date_source) == (date(2026, 3, 15), "selector:span.when")
    time_tag = '<time itemprop="datePublished" datetime="2026-01-02">'
    assert extract(page(body=f"{time_tag}</time><h1>{TITLE}</h1>{PARA}")).published_date == date(2026, 1, 2)


def test_fallback_extractors_in_order(monkeypatch):
    body = "খবরের মূল অংশ। " * 30
    json_ld = extract(page(ld(f'{{"@type":"NewsArticle","headline":"{TITLE}","articleBody":"{body}","author":{{"name":"রিপোর্টার"}}}}'),
                           body="<div>শুধু মেনু</div>"))
    assert json_ld.extraction_method == ExtractionMethod.JSON_LD and json_ld.author == "রিপোর্টার"

    generic = page(body=f'<h1>{TITLE}</h1><div class="news-details">{PARA}</div>')
    monkeypatch.setattr(s06.trafilatura, "extract", lambda *a, **k: body)
    via_trafilatura = extract(generic)
    assert via_trafilatura.extraction_method == ExtractionMethod.TRAFILATURA
    assert via_trafilatura.title == TITLE  # the " | প্রথম আলো" suffix is removed
    monkeypatch.setattr(s06.trafilatura, "extract", lambda *a, **k: None)
    assert extract(generic).extraction_method == ExtractionMethod.READABILITY
    monkeypatch.setattr(s06, "Document", lambda html: (_ for _ in ()).throw(ValueError("no readability")))
    by_class = extract(generic)
    assert by_class.extraction_method == ExtractionMethod.BEAUTIFULSOUP and by_class.has_body

    description = "বিবরণ " * 40
    meta_only = extract(f'<html><head><meta property="og:title" content="{TITLE}">'
                        f'<meta property="og:description" content="{description}"></head><body></body></html>')
    assert meta_only.extraction_method == ExtractionMethod.OPENGRAPH and meta_only.title == TITLE


def test_a_generic_aggregator_title_is_replaced_by_the_search_title():
    candidate = CandidateArticleSchema(url=URL, title_snippet=TITLE, search_provider=SearchProvider.PY_GOOGLE_NEWS,
                                       query_type="headline")
    html = f"<html><head><title>Google News</title></head><body>{PARA}{PARA}</body></html>"
    a = extract(html, candidate=candidate)
    assert a.title == TITLE and a.search_provider == SearchProvider.PY_GOOGLE_NEWS


def test_kicker_lines_next_to_the_title_are_headline_variants():
    kicker_html = """<div><h2>প্রধানমন্ত্রীর সঙ্গে আবরার ফাহাদের পরিবারের সাক্ষাৎ</h2>
      <h1>রায় দ্রুত কার্যকরের দাবি</h1><div>স্টাফ রিপোর্টার</div></div>"""
    assert _headline_variants(BeautifulSoup(kicker_html, "html.parser"), "রায় দ্রুত কার্যকরের দাবি") == [
        "প্রধানমন্ত্রীর সঙ্গে আবরার ফাহাদের পরিবারের সাক্ষাৎ",
        "প্রধানমন্ত্রীর সঙ্গে আবরার ফাহাদের পরিবারের সাক্ষাৎ রায় দ্রুত কার্যকরের দাবি",
    ]
    linked = BeautifulSoup('<div><h1>শিরোনাম এখানে</h1><h2><a href="/x">আরও খবর পড়ুন এখানে</a></h2></div>', "html.parser")
    assert _headline_variants(linked, "শিরোনাম এখানে") == []  # a linked heading is not a kicker
    assert _headline_variants(linked, None) == []


async def test_stage_keeps_readable_pages_and_counts_the_rest_as_failures(monkeypatch):
    ctx = make_context(TITLE)
    ctx.fetched_html = {URL: page(), "https://www.prothomalo.com/empty/99999": "<html></html>",
                        "https://www.prothomalo.com/boom/12345": page()}
    original = ArticleExtractorStage._extract_one

    def flaky(self, url, *args):
        if "boom" in url:
            raise RuntimeError("parser crashed")
        return original(self, url, *args)

    monkeypatch.setattr(ArticleExtractorStage, "_extract_one", flaky)
    out = await ArticleExtractorStage(MagicMock()).execute(ctx)
    assert [a.url for a in out.extracted_articles] == [URL]
    assert (out.extraction_attempted, out.extraction_errors, len(out.failed_extraction_urls)) == (3, 2, 2)


async def test_verified_sources_pages_use_their_own_publishers_selectors():
    ctx = make_context(TITLE)
    ctx.verification_mode = source_policy.VERIFIED_SOURCES
    cfg = {"title_selectors": ["h2.headline"], "body_selectors": ["div.story"]}
    ctx.verified_scope = source_policy.VerifiedScope([source_policy.VerifiedPublisher("jugantor.com", "j", ["jugantor.com"], cfg)])
    url = "https://www.jugantor.com/national/123456"
    ctx.fetched_html = {url: page(body=f'<h2 class="headline">যুগান্তরের শিরোনাম</h2><div class="story">{PARA}{PARA}</div>')}
    [a] = (await ArticleExtractorStage(MagicMock()).execute(ctx)).extracted_articles
    assert a.title == "যুগান্তরের শিরোনাম" and a.extraction_method == ExtractionMethod.SOURCE_SPECIFIC
    assert (await ArticleExtractorStage(MagicMock()).execute(make_context(TITLE))).extracted_articles == []
