"""The outlet's own search page: full query, on-domain article links with
their headline text, and page chrome never mistaken for results."""

import httpx
import pytest

from app.features.search.internal_site_client import (
    InternalSiteSearchClient,
    InternalSiteSearchError,
)

CONFIG = {"internal_search_url": "https://www.prothomalo.com/search?q={query}", "article_url_patterns": []}
QUERY = "সরকার নতুন সেতু উদ্বোধন R&D #report"


async def search(html: str | int, query: str = QUERY, config=CONFIG):
    seen = []

    def handler(request):
        seen.append(request.url.params.get("q"))
        return httpx.Response(html, text="err") if isinstance(html, int) else httpx.Response(200, text=html)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        results = await InternalSiteSearchClient(http).search_entries(query, domain="prothomalo.com", source_config=config)
    return results, seen


async def test_results_are_on_domain_articles_with_headline_text():
    html = """
      <div class="card"><a href="/bangladesh/abc12345xyz"><img></a>
        <h3><a href="/bangladesh/abc12345xyz">সরকার নতুন সেতু উদ্বোধন করেছে</a></h3></div>
      <h2>সেতু উদ্বোধনে মন্ত্রী<a href="https://www.prothomalo.com/politics/def67890uvw"><img></a></h2>
      <a href="https://evil.example/news/abc12345xyz">সরকার সেতু ভুয়া খবর</a>
      <a href="/tag/setu">সেতু ট্যাগ</a><a href="#top">উপরে</a>
    """
    results, seen = await search(html)
    assert seen == [QUERY]  # the full query, every keyword kept
    assert results == [
        ("https://www.prothomalo.com/bangladesh/abc12345xyz", "সরকার নতুন সেতু উদ্বোধন করেছে"),
        ("https://www.prothomalo.com/politics/def67890uvw", "সেতু উদ্বোধনে মন্ত্রী"),  # text from the heading
    ]


async def test_a_page_of_unrelated_latest_news_is_not_a_result_set():
    chrome = '<a href="/sports/abc12345xyz">ক্রিকেট দলের অনুশীলন শুরু</a><a href="/world/def67890uvw">বিশ্বের খবর আজকের</a>'
    assert (await search(chrome))[0] == []


async def test_unconfigured_failed_and_empty_searches():
    assert await search("<html></html>", config={}) == ([], [])
    assert await search("<html></html>", query="site:prothomalo.com") == ([], [])
    with pytest.raises(InternalSiteSearchError):  # a failure is never an empty search
        await search(503)
