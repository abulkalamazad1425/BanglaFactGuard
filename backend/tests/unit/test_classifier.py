"""
tests/unit/test_classifier.py
==============================
Unit tests for Stage 11: Verdict Classifier (`ClassifierStage`).

Covers the 3-dimensional verdict model: source_status (CONFIRMED | NOT_FOUND),
content_status (MATCHED | ALTERED, only set when source is CONFIRMED), and
date_status (MATCHED | MISMATCHED, only set when both dates are known).
"""

import pytest
from datetime import date
from app.features.verification.pipeline.stages.s11_classifier import ClassifierStage
from app.features.verification.pipeline.context import PipelineContext, build_context
from app.core.constants import ContentStatus, DateStatus, SourceStatus, SearchProvider, ExtractionMethod
from app.features.articles.schemas import RankedArticleSchema
from app.features.verification.schemas import (
    VerificationScoresSchema,
    ManipulationFlagsSchema,
)


@pytest.fixture
def base_context() -> PipelineContext:
    """Provide a standard context template for testing classification."""
    context = build_context(
        headline="রোহিঙ্গা ক্যাম্পে নতুন ফ্লাইওভার",
        claimed_source="prothomalo.com",
    )
    context.normalized_headline = context.raw_headline
    context.normalized_source = "prothomalo.com"
    return context


@pytest.fixture
def dummy_article() -> RankedArticleSchema:
    """Provide a dummy matching article."""
    return RankedArticleSchema(
        url="https://prothomalo.com/article/123",
        title="রোহিঙ্গা ক্যাম্পে নতুন ফ্লাইওভার উদ্বোধন",
        body="রোহিঙ্গা ক্যাম্পে নতুন ফ্লাইওভার উদ্বোধন করলেন প্রধানমন্ত্রী শেখ হাসিনা।",
        author="নিজস্ব প্রতিবেদক",
        published_date=date(2026, 6, 7),
        rank_score=0.90,
        search_provider=SearchProvider.BRAVE,
        extraction_method=ExtractionMethod.TRAFILATURA,
    )


@pytest.mark.asyncio
async def test_classifier_not_found_no_evidence(base_context):
    """source_status is NOT_FOUND when no evidence is retrieved at all;
    content_status and date_status are left unset — there's nothing to
    compare against when the source never published the story."""
    stage = ClassifierStage()
    context = await stage.execute(base_context)

    assert context.source_status == SourceStatus.NOT_FOUND
    assert context.content_status is None
    assert context.date_status is None
    assert context.confidence == 0.95
    assert "No article matching the claim" in context.reasoning


@pytest.mark.asyncio
async def test_classifier_not_found_unrelated_article(base_context, dummy_article):
    """An article was retrieved, but its semantic similarity is too low to be
    the claimed story — still NOT_FOUND, not a content mismatch."""
    base_context.ranked_articles = [dummy_article]
    base_context.top_article = dummy_article
    base_context.scores = VerificationScoresSchema(
        semantic_similarity=0.10,
        entity_match=0.05,
        keyword_overlap=0.05,
        numerical_consistency=1.0,
        contradiction_score=0.0,
    )

    stage = ClassifierStage()
    context = await stage.execute(base_context)

    assert context.source_status == SourceStatus.NOT_FOUND
    assert context.content_status is None
    assert context.date_status is None


@pytest.mark.asyncio
async def test_classifier_confirmed_and_matched(base_context, dummy_article):
    """source CONFIRMED + content MATCHED under strong similarity and no
    contradiction — the paraphrase/same-meaning case."""
    base_context.ranked_articles = [dummy_article]
    base_context.top_article = dummy_article
    base_context.scores = VerificationScoresSchema(
        semantic_similarity=0.92,
        entity_match=0.90,
        keyword_overlap=0.85,
        numerical_consistency=1.0,
        contradiction_score=0.02,
    )
    base_context.manipulation_flags = ManipulationFlagsSchema(
        headline_manipulated=False,
        body_altered=False,
        numbers_altered=False,
        entities_replaced=False,
    )

    stage = ClassifierStage()
    context = await stage.execute(base_context)

    assert context.source_status == SourceStatus.CONFIRMED
    assert context.content_status == ContentStatus.MATCHED
    assert context.confidence >= 0.85
    assert "source CONFIRMED" in context.reasoning
    assert "content MATCHED" in context.reasoning


@pytest.mark.asyncio
async def test_classifier_confirmed_and_altered_on_contradiction(base_context, dummy_article):
    """A high NLI contradiction score forces content_status to ALTERED even
    though the source is CONFIRMED — outright contradiction, not a source
    problem."""
    base_context.ranked_articles = [dummy_article]
    base_context.top_article = dummy_article

    base_context.scores = VerificationScoresSchema(
        semantic_similarity=0.50,
        entity_match=0.60,
        keyword_overlap=0.40,
        numerical_consistency=1.0,
        contradiction_score=0.85,
    )
    base_context.manipulation_flags = ManipulationFlagsSchema(
        headline_manipulated=False,
        body_altered=False,
        numbers_altered=False,
        entities_replaced=False,
    )

    stage = ClassifierStage()
    context = await stage.execute(base_context)

    assert context.source_status == SourceStatus.CONFIRMED
    assert context.content_status == ContentStatus.ALTERED
    assert context.confidence >= 0.75
    assert "content ALTERED" in context.reasoning


@pytest.mark.asyncio
async def test_classifier_confirmed_and_altered_on_manipulation(base_context, dummy_article):
    """Detected manipulation forces content_status to ALTERED even on high
    similarity scores — a manipulated headline is not a MATCHED claim."""
    base_context.ranked_articles = [dummy_article]
    base_context.top_article = dummy_article
    base_context.scores = VerificationScoresSchema(
        semantic_similarity=0.90,
        entity_match=0.90,
        keyword_overlap=0.80,
        numerical_consistency=1.0,
        contradiction_score=0.05,
    )

    base_context.manipulation_flags = ManipulationFlagsSchema(
        headline_manipulated=True,
        body_altered=False,
        numbers_altered=False,
        entities_replaced=False,
    )

    stage = ClassifierStage()
    context = await stage.execute(base_context)

    assert context.source_status == SourceStatus.CONFIRMED
    assert context.content_status == ContentStatus.ALTERED
    assert "Headline appears to have been manipulated" in context.reasoning


@pytest.mark.asyncio
async def test_classifier_date_matched(base_context, dummy_article):
    """date_status is MATCHED when the claimed publication date equals the
    source article's actual date."""
    base_context.published_date = date(2026, 6, 7)  # same as dummy_article
    base_context.ranked_articles = [dummy_article]
    base_context.top_article = dummy_article
    base_context.scores = VerificationScoresSchema(
        semantic_similarity=0.92,
        entity_match=0.90,
        keyword_overlap=0.85,
        numerical_consistency=1.0,
        contradiction_score=0.02,
    )

    stage = ClassifierStage()
    context = await stage.execute(base_context)

    assert context.source_status == SourceStatus.CONFIRMED
    assert context.content_status == ContentStatus.MATCHED
    assert context.date_status == DateStatus.MATCHED
    assert "date MATCHED" in context.reasoning


@pytest.mark.asyncio
async def test_classifier_date_mismatched_does_not_affect_content(base_context, dummy_article):
    """A claimed date that differs from the source's actual date is
    date_status MISMATCHED — and must NOT demote content_status, which stays
    MATCHED on its own evidence."""
    base_context.published_date = date(2020, 1, 1)  # differs from dummy_article's 2026-06-07
    base_context.ranked_articles = [dummy_article]
    base_context.top_article = dummy_article
    base_context.scores = VerificationScoresSchema(
        semantic_similarity=0.92,
        entity_match=0.90,
        keyword_overlap=0.85,
        numerical_consistency=1.0,
        contradiction_score=0.02,
    )

    stage = ClassifierStage()
    context = await stage.execute(base_context)

    assert context.source_status == SourceStatus.CONFIRMED
    assert context.content_status == ContentStatus.MATCHED
    assert context.date_status == DateStatus.MISMATCHED
    assert "date MISMATCHED" in context.reasoning


@pytest.mark.asyncio
async def test_classifier_date_unknown_when_dates_missing(base_context, dummy_article):
    """date_status stays unset (None) when the claim supplied no publication
    date — there's nothing to compare, and this must not be reported as a
    mismatch."""
    base_context.published_date = None
    base_context.ranked_articles = [dummy_article]
    base_context.top_article = dummy_article
    base_context.scores = VerificationScoresSchema(
        semantic_similarity=0.92,
        entity_match=0.90,
        keyword_overlap=0.85,
        numerical_consistency=1.0,
        contradiction_score=0.02,
    )

    stage = ClassifierStage()
    context = await stage.execute(base_context)

    assert context.date_status is None
    assert "date UNKNOWN" in context.reasoning
