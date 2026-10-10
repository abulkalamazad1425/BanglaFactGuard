"""S03: source-restricted queries from the headline only (never the body)."""

from datetime import date
from unittest.mock import patch

import pytest

from app.core.constants import QueryType
from app.core.exceptions import QueryGenerationError
from app.features.verification import source_policy
from app.features.verification.pipeline.context import build_context
from app.features.verification.pipeline.stages.s03_query_generator import QueryGeneratorStage

MODULE = "app.features.verification.pipeline.stages.s03_query_generator"
KEYWORDS = ["bridge", "river", "city", "opened", "minister", "traffic", "public", "today"]
HEADLINE = "New bridge opened for public traffic today"


def context(published=None, body=None, source="prothomalo.com"):
    ctx = build_context(headline=HEADLINE, claimed_source=source, published_date=published, news_body=body)
    ctx.normalized_headline, ctx.normalized_source, ctx.normalized_body = ctx.raw_headline, source, body
    return ctx


async def generate(ctx, keywords=KEYWORDS):
    with patch(f"{MODULE}.extract_headline_keywords", return_value=keywords):
        return await QueryGeneratorStage().execute(ctx)


@pytest.mark.parametrize("dated", [False, True])
async def test_headline_all_keywords_and_short_keyword_queries_restricted_to_the_source(dated):
    ctx = await generate(context(date(2026, 10, 4) if dated else None))
    base = [(f"site:prothomalo.com {HEADLINE}", QueryType.HEADLINE.value),
            ("site:prothomalo.com " + " ".join(KEYWORDS), QueryType.KEYWORDS.value)]
    expected = base + [("site:prothomalo.com " + " ".join(KEYWORDS[:n]), QueryType.KEYWORDS.value) for n in (3, 4)]
    if dated:
        expected += [(q + " 04 October 2026", QueryType.DATE_BOUND.value) for q, _ in base]
    assert ctx.search_queries == expected and ctx.claim_keywords == KEYWORDS


@pytest.mark.parametrize("keywords,extra", [
    ([], None),                                   # only the headline query
    (["bridge", "river"], []),
    (["bridge", "river", "city"], []),            # first 3 == all keywords: not repeated
    (["bridge", "river", "city", "opened", "minister"], ["bridge river city", "bridge river city opened"]),
])
async def test_short_keyword_queries_only_when_available_and_never_duplicated(keywords, extra):
    ctx = await generate(context(), keywords)
    texts = [q.removeprefix("site:prothomalo.com ") for q, _ in ctx.search_queries]
    assert texts == ([HEADLINE] if extra is None else [HEADLINE, " ".join(keywords), *extra])


async def test_the_body_and_site_operators_in_the_text_never_shape_the_search():
    plain = await generate(context())
    with_body = await generate(context(body="Completely unrelated body keywords"))
    assert plain.search_queries == with_body.search_queries
    tricky = context()
    tricky.normalized_headline = "site:evil.com " + HEADLINE
    assert all("evil.com" not in q for q, _ in (await generate(tricky)).search_queries)


async def test_without_a_source_nothing_is_generated():
    with pytest.raises(QueryGenerationError):
        await generate(context(source=None))


def verified_context(*publishers):
    ctx = context(source=None)
    ctx.verification_mode = source_policy.VERIFIED_SOURCES
    ctx.verified_scope = source_policy.VerifiedScope(
        [source_policy.VerifiedPublisher(p, p, [p], {}) for p in publishers]
    )
    return ctx


async def test_verified_sources_mode_has_bounded_queries_without_a_site_operator():
    ctx = await generate(verified_context("jugantor.com", "prothomalo.com"))
    assert ctx.search_queries == [
        (HEADLINE, QueryType.HEADLINE.value),
        (" ".join(KEYWORDS), QueryType.KEYWORDS.value),
        (" ".join(KEYWORDS[:4]), QueryType.KEYWORDS.value),
    ]
    with pytest.raises(QueryGenerationError):  # no active verified source: nothing may be searched
        await generate(verified_context())
