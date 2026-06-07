"""
tests/unit/test_classifier.py
==============================
Unit tests for Stage 11: Verdict Classifier (`ClassifierStage`).
"""

import pytest
from datetime import date
from app.pipelines.stages.s11_classifier import ClassifierStage
from app.pipelines.context import PipelineContext, build_context
from app.core.constants import VerificationLabel, SearchProvider, ExtractionMethod
from app.schemas.article import RankedArticleSchema
from app.schemas.scores import VerificationScoresSchema, ManipulationFlagsSchema

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
async def test_classifier_not_found(base_context):
    """Verify verdict is NOT_FOUND_IN_CLAIMED_SOURCE when no evidence is retrieved."""
    stage = ClassifierStage()
    context = await stage.execute(base_context)

    assert context.label == VerificationLabel.NOT_FOUND_IN_CLAIMED_SOURCE
    assert context.confidence == 0.95
    assert "No article matching the claim" in context.reasoning

@pytest.mark.asyncio
async def test_classifier_true_verdict(base_context, dummy_article):
    """Verify claim is marked TRUE under strong similarity and no contradiction."""
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

    assert context.label == VerificationLabel.TRUE
    assert context.confidence >= 0.85
    assert "Verdict: The claim is TRUE" in context.reasoning

@pytest.mark.asyncio
async def test_classifier_false_verdict_nli(base_context, dummy_article):
    """Verify high contradiction score overrides verdict to FALSE."""
    base_context.ranked_articles = [dummy_article]
    base_context.top_article = dummy_article
    # High contradiction
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

    assert context.label == VerificationLabel.FALSE
    assert context.confidence >= 0.75
    assert "Verdict: The claim is FALSE" in context.reasoning

@pytest.mark.asyncio
async def test_classifier_partially_true_manipulation(base_context, dummy_article):
    """Verify manipulation detection forces label to PARTIALLY_TRUE even on high similarity."""
    base_context.ranked_articles = [dummy_article]
    base_context.top_article = dummy_article
    base_context.scores = VerificationScoresSchema(
        semantic_similarity=0.90,
        entity_match=0.90,
        keyword_overlap=0.80,
        numerical_consistency=1.0,
        contradiction_score=0.05,
    )
    # Headline manipulated flag set
    base_context.manipulation_flags = ManipulationFlagsSchema(
        headline_manipulated=True,
        body_altered=False,
        numbers_altered=False,
        entities_replaced=False,
    )

    stage = ClassifierStage()
    context = await stage.execute(base_context)

    assert context.label == VerificationLabel.PARTIALLY_TRUE
    assert "Headline appears to have been manipulated" in context.reasoning
