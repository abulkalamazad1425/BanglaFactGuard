
import pytest
from app.features.verification.pipeline.stages.s01_normalizer import InputNormalizerStage
from app.features.verification.pipeline.context import PipelineContext, build_context
from app.core.exceptions import NormalizationError
from app.features.sources.repository import SourceRepository
from app.features.sources.models import VerifiedSource

@pytest.mark.asyncio
async def test_normalize_text_basic():
    context = build_context(
        headline="  প্রথম  আলো  \u200b",
        claimed_source="prothomalo.com",
    )
    
    stage = InputNormalizerStage(source_repo=None)
    context = await stage.execute(context)
    

    assert context.normalized_headline == "প্রথম আলো"
    assert context.normalized_body is None

@pytest.mark.asyncio
async def test_normalize_empty_headline_raises_error():
    context = build_context(
        headline="   \u200b   ",
        claimed_source="prothomalo.com",
    )
    
    stage = InputNormalizerStage(source_repo=None)
    with pytest.raises(NormalizationError):
        await stage.execute(context)

@pytest.mark.asyncio
async def test_resolve_source_via_url():
    context = build_context(
        headline="কিছু খবর",
        claimed_source="https://www.thedailystar.net/news/bangladesh-123",
    )
    
    stage = InputNormalizerStage(source_repo=None)
    context = await stage.execute(context)
    
    assert context.normalized_source == "thedailystar.net"

@pytest.mark.asyncio
async def test_resolve_source_via_static_alias():
    context = build_context(
        headline="কিছু খবর",
        claimed_source="প্রথম আলো",
    )
    
    stage = InputNormalizerStage(source_repo=None)
    context = await stage.execute(context)
    
    assert context.normalized_source == "prothomalo.com"

@pytest.mark.asyncio
async def test_resolve_source_via_db(db_session):
    source_repo = SourceRepository(db_session)
    

    custom_source = VerifiedSource(
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
    context = build_context(
        headline="কিছু খবর",
        claimed_source="অপরিচিত উৎস",
    )
    

    import unittest.mock
    mock_repo = unittest.mock.AsyncMock(spec=SourceRepository)
    mock_repo.resolve_source.return_value = None

    stage = InputNormalizerStage(source_repo=mock_repo)
    context = await stage.execute(context)
    
    assert context.normalized_source is None

    assert context.claim_hash is not None

