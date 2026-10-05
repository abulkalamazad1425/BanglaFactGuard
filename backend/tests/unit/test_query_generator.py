from datetime import date
from unittest.mock import patch

import pytest

from app.core.constants import QueryType
from app.core.exceptions import QueryGenerationError
from app.features.verification.pipeline.context import build_context
from app.features.verification.pipeline.stages.s03_query_generator import QueryGeneratorStage

MODULE = "app.features.verification.pipeline.stages.s03_query_generator"
KEYWORDS = ["bridge", "river", "city", "opened", "minister", "traffic", "public", "today"]


def context(published=None, body=None):
    ctx = build_context(headline="New bridge opened for public traffic today",
                        claimed_source="prothomalo.com", published_date=published,
                        news_body=body)
    ctx.normalized_headline = ctx.raw_headline
    ctx.normalized_source = "prothomalo.com"
    ctx.normalized_body = body
    return ctx


@pytest.mark.asyncio
@pytest.mark.parametrize("dated", [False, True])
async def test_all_keywords_in_one_source_restricted_query(dated):
    ctx = context(date(2026, 10, 4) if dated else None)
    with patch(f"{MODULE}.extract_headline_keywords", return_value=KEYWORDS) as extract:
        await QueryGeneratorStage().execute(ctx)
    extract.assert_called_once_with(ctx.normalized_headline, top_n=8)
    base = [(f"site:prothomalo.com {ctx.normalized_headline}", QueryType.HEADLINE.value),
            ("site:prothomalo.com " + " ".join(KEYWORDS), QueryType.KEYWORDS.value)]
    expected = base + [("site:prothomalo.com " + " ".join(KEYWORDS[:3]), QueryType.KEYWORDS.value),
                       ("site:prothomalo.com " + " ".join(KEYWORDS[:4]), QueryType.KEYWORDS.value)]
    if dated:
        expected += [(q + " 04 October 2026", QueryType.DATE_BOUND.value) for q, _ in base]
    assert ctx.search_queries == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("keywords,extra", [
    (["bridge", "river"], []),
    (["bridge", "river", "city"], []),  # first 3 == all keywords: not repeated
    (["bridge", "river", "city", "opened"], ["bridge river city"]),
    (["bridge", "river", "city", "opened", "minister"], ["bridge river city", "bridge river city opened"]),
])
async def test_first_three_and_four_keyword_queries_only_when_available(keywords, extra):
    ctx = context()
    with patch(f"{MODULE}.extract_headline_keywords", return_value=keywords):
        await QueryGeneratorStage().execute(ctx)
    texts = [q.removeprefix("site:prothomalo.com ") for q, _ in ctx.search_queries]
    assert texts == [ctx.normalized_headline, " ".join(keywords), *extra]


@pytest.mark.asyncio
async def test_body_and_entities_do_not_change_search():
    plain = context()
    with_body = context(body="Completely unrelated body keywords must never be searched")
    with_body.claim_entities = ["Another entity"]
    with patch(f"{MODULE}.extract_headline_keywords", return_value=KEYWORDS):
        await QueryGeneratorStage().execute(plain)
        await QueryGeneratorStage().execute(with_body)
    assert plain.search_queries == with_body.search_queries
    assert with_body.normalized_body  # still available for content verification


@pytest.mark.asyncio
async def test_duplicate_headline_and_keywords_are_not_searched_twice():
    ctx = context(date(2026, 10, 4))
    with patch(f"{MODULE}.extract_headline_keywords", return_value=ctx.normalized_headline.split()):
        await QueryGeneratorStage().execute(ctx)
    texts = [q for q, _ in ctx.search_queries]
    assert len(texts) == len(set(texts)) == 4  # headline, first 3, first 4, headline + date


@pytest.mark.asyncio
async def test_missing_keywords_keeps_valid_headline_search():
    ctx = context()
    with patch(f"{MODULE}.extract_headline_keywords", return_value=[]):
        await QueryGeneratorStage().execute(ctx)
    assert len(ctx.search_queries) == 1


@pytest.mark.asyncio
async def test_missing_source_never_generates_unrestricted_search():
    ctx = context()
    ctx.normalized_source = None
    with pytest.raises(QueryGenerationError):
        await QueryGeneratorStage().execute(ctx)
