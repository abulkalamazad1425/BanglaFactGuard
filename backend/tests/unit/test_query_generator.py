"""
tests/unit/test_query_generator.py
====================================
Unit tests for Stage 3: Search Query Generator (`QueryGeneratorStage`).
"""

import pytest
from datetime import date
from app.features.verification.pipeline.stages.s03_query_generator import (
    QueryGeneratorStage,
)
from app.features.verification.pipeline.context import PipelineContext, build_context
from app.core.constants import QueryType


@pytest.mark.asyncio
async def test_query_generation_basic():
    """Verify standard headline and keyword query variants are generated."""
    context = build_context(
        headline="প্রধানমন্ত্রী শেখ হাসিনা নতুন ফ্লাইওভার উদ্বোধন করলেন",
        claimed_source="prothomalo.com",
    )

    context.normalized_headline = context.raw_headline

    stage = QueryGeneratorStage()
    context = await stage.execute(context)

    assert len(context.search_queries) >= 1

    assert context.search_queries[0] == (
        context.normalized_headline,
        QueryType.HEADLINE.value,
    )

    keyword_queries = [
        q for q, t in context.search_queries if t == QueryType.KEYWORDS.value
    ]
    assert len(keyword_queries) <= 1


@pytest.mark.asyncio
async def test_query_generation_with_date():
    """Verify that a date-bound query is generated when published_date is set."""
    context = build_context(
        headline="রোহিঙ্গা ক্যাম্পে অগ্নিকাণ্ড",
        claimed_source="prothomalo.com",
        published_date=date(2026, 5, 20),
    )
    context.normalized_headline = context.raw_headline

    stage = QueryGeneratorStage()
    context = await stage.execute(context)

    date_bound_queries = [
        q for q, t in context.search_queries if t == QueryType.DATE_BOUND.value
    ]
    assert len(date_bound_queries) == 1
    assert "2026 May 20" in date_bound_queries[0]


@pytest.mark.asyncio
async def test_query_generation_with_body():
    """Verify that body-summary query is generated when body text is available."""
    context = build_context(
        headline="বাজেট ২০২৬ ঘোষণা",
        claimed_source="prothomalo.com",
        news_body="অর্থমন্ত্রী জাতীয় সংসদে নতুন অর্থ বছরের বাজেট পেশ করছেন। এতে শিক্ষা খাতে বরাদ্দ বৃদ্ধি করা হয়েছে।",
    )
    context.normalized_headline = context.raw_headline
    context.normalized_body = context.raw_news_body

    stage = QueryGeneratorStage()
    context = await stage.execute(context)

    body_summary_queries = [
        q for q, t in context.search_queries if t == QueryType.BODY_SUMMARY.value
    ]
    assert len(body_summary_queries) == 1


@pytest.mark.asyncio
async def test_query_generation_max_limit():
    """Verify that queries list does not exceed MAX_SEARCH_QUERIES (5)."""
    context = build_context(
        headline="এই খবরটি অনেক বড় এবং এতে অনেক রকম তথ্য রয়েছে",
        claimed_source="prothomalo.com",
        news_body="এখানে অনেক লম্বা বডি টেক্সট আছে যাতে ৫টি এর বেশি কুয়েরি জেনারেট হতে পারে সহজে।",
        published_date=date(2026, 6, 7),
    )
    context.normalized_headline = context.raw_headline
    context.normalized_body = context.raw_news_body
    context.claim_entities = ["খবর", "তথ্য", "বডি"]

    stage = QueryGeneratorStage()
    context = await stage.execute(context)

    assert len(context.search_queries) <= 5
