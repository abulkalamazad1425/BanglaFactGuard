"""
tests/unit/test_normalizer.py
==============================
Unit tests for Stage 1: Input Normalizer (`InputNormalizerStage`).
"""

import pytest
from app.features.verification.pipeline.stages.s01_normalizer import InputNormalizerStage
from app.features.verification.pipeline.context import PipelineContext, build_context
from app.core.exceptions import NormalizationError
from app.features.sources.repository import SourceRepository
from app.features.source_registry import SourceRegistry

@pytest.mark.asyncio
async def test_normalize_text_basic():
    """Verify that basic Unicode normalization and spacing is applied."""
    context = build_context(
        headline="  প্রথম  আলো  \u200b",  # has zero-width space and extra spaces
        claimed_source="prothomalo.com",
    )
    
    stage = InputNormalizerStage(source_repo=None)
    context = await stage.execute(context)
    
    # Assert extra whitespaces collapsed, zero-width space removed
    assert context.normalized_headline == "প্রথম আলো"
    assert context.normalized_body is None

@pytest.mark.asyncio
async def test_normalize_empty_headline_raises_error():
    """Verify that an empty or whitespace-only headline raises NormalizationError."""
    context = build_context(
        headline="   \u200b   ",
        claimed_source="prothomalo.com",
    )
    
    stage = InputNormalizerStage(source_repo=None)
    with pytest.raises(NormalizationError):
        await stage.execute(context)

@pytest.mark.asyncio
async def test_resolve_source_via_url():
    """Verify source is resolved if raw_claimed_source is a URL."""
    context = build_context(
        headline="কিছু খবর",
        claimed_source="https://www.thedailystar.net/news/bangladesh-123",
    )
    
    stage = InputNormalizerStage(source_repo=None)
    context = await stage.execute(context)
    
    assert context.normalized_source == "thedailystar.net"

@pytest.mark.asyncio
async def test_resolve_source_via_static_alias():
    """Verify source is resolved via static alias map."""
    context = build_context(
        headline="কিছু খবর",
        claimed_source="প্রথম আলো",
    )
    
    stage = InputNormalizerStage(source_repo=None)
    context = await stage.execute(context)
    
    assert context.normalized_source == "prothomalo.com"

@pytest.mark.asyncio
async def test_resolve_source_via_db(db_session):
    """Verify source is resolved via DB repository when alias map/URL falls through."""
    source_repo = SourceRepository(db_session)
    
    # Insert a custom source in SQLite test DB
    custom_source = SourceRegistry(
        canonical_name="customportal.com",
        display_name="Custom Portal",
        aliases=["কাস্টম পোর্টাল", "customportal"],
        base_url="https://customportal.com",
        is_active=True,
    )
    db_session.add(custom_source)
    await db_session.flush()

    context = build_context(
        headline="কিছু খবর",
        claimed_source="কাস্টম পোর্টাল",
    )
    
    stage = InputNormalizerStage(source_repo=source_repo)
    context = await stage.execute(context)
    
    assert context.normalized_source == "customportal.com"

@pytest.mark.asyncio
async def test_resolve_source_unresolved_falls_back():
    """Verify unresolved source is handled gracefully (retains None, hash computed)."""
    context = build_context(
        headline="কিছু খবর",
        claimed_source="অপরিচিত উৎস",
    )
    
    # Mock source repo to return None
    import unittest.mock
    mock_repo = unittest.mock.AsyncMock(spec=SourceRepository)
    mock_repo.resolve_source.return_value = None

    stage = InputNormalizerStage(source_repo=mock_repo)
    context = await stage.execute(context)
    
    assert context.normalized_source is None
    # Verify hash is still computed using raw_claimed_source
    assert context.claim_hash is not None

