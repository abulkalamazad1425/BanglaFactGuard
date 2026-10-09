import pytest
from unittest.mock import AsyncMock, MagicMock
from app.features.verification.pipeline.stages.s01_normalizer import (
    InputNormalizerStage,
)
from app.features.verification.pipeline.context import PipelineContext, build_context
from app.core.exceptions import NormalizationError
from app.features.sources.repository import SourceRepository
from app.features.sources.models import VerifiedSource


# S01 looks the resolved source up in the registry; a stub with no record is
# enough for these normalisation tests.
_REPO = MagicMock(
    get_by_canonical_name=AsyncMock(return_value=None),
    resolve_source=AsyncMock(return_value=None),
)


@pytest.mark.asyncio
async def test_normalize_text_basic():
    context = build_context(
        headline="  প্রথম  আলো  \u200b",
        claimed_source="prothomalo.com",
    )

    stage = InputNormalizerStage(source_repo=_REPO)
    context = await stage.execute(context)

    assert context.normalized_headline == "প্রথম আলো"
    assert context.normalized_body is None


@pytest.mark.asyncio
async def test_normalize_empty_headline_raises_error():
    context = build_context(
        headline="   \u200b   ",
        claimed_source="prothomalo.com",
    )

    stage = InputNormalizerStage(source_repo=_REPO)
    with pytest.raises(NormalizationError):
        await stage.execute(context)


@pytest.mark.asyncio
async def test_resolve_source_via_url():
    context = build_context(
        headline="কিছু খবর",
        claimed_source="https://www.thedailystar.net/news/bangladesh-123",
    )

    stage = InputNormalizerStage(source_repo=_REPO)
    context = await stage.execute(context)

    assert context.normalized_source == "thedailystar.net"


@pytest.mark.asyncio
async def test_resolve_source_via_static_alias():
    context = build_context(
        headline="কিছু খবর",
        claimed_source="প্রথম আলো",
    )

    stage = InputNormalizerStage(source_repo=_REPO)
    context = await stage.execute(context)

    assert context.normalized_source == "prothomalo.com"


@pytest.mark.asyncio
async def test_resolve_source_via_db(db_session, monkeypatch):
    source_repo = SourceRepository(db_session)

    # `get_by_alias` uses the Postgres JSONB containment operator (`@>`), which
    # SQLite cannot execute. Same semantics (exact alias of an active source),
    # evaluated in Python, so the rest of the DB-backed path is still real.
    async def sqlite_get_by_alias(alias):
        from sqlalchemy import select

        rows = (await db_session.execute(select(VerifiedSource))).scalars().all()
        return next((s for s in rows if s.is_active and alias in (s.aliases or [])), None)

    monkeypatch.setattr(source_repo, "get_by_alias", sqlite_get_by_alias)

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
async def test_unresolved_source_fails_closed(monkeypatch):
    """With the verified-sources fallback disabled, S01 never lets an
    unresolved source through (that would search the whole web instead of the
    claimed outlet): it raises NormalizationError."""
    from app.features.verification import source_policy

    monkeypatch.setattr(source_policy, "fallback_enabled", lambda: False)
    context = build_context(
        headline="কিছু খবর",
        claimed_source="অপরিচিত উৎস",
    )

    import unittest.mock

    mock_repo = unittest.mock.AsyncMock(spec=SourceRepository)
    mock_repo.resolve_source.return_value = None

    stage = InputNormalizerStage(source_repo=mock_repo)
    with pytest.raises(NormalizationError):
        await stage.execute(context)


@pytest.mark.asyncio
async def test_identity_hash_includes_body_and_claimed_date():
    from datetime import date

    base = dict(headline="কিছু খবর", claimed_source="prothomalo.com")
    hashes = []
    for kw in ({}, {"published_date": date(2026, 6, 7)}, {"published_date": date(2026, 6, 8)},
               {"news_body": "বডি এক"}, {"news_body": "বডি দুই"}):
        ctx = await InputNormalizerStage(source_repo=_REPO).execute(build_context(**base, **kw))
        hashes.append(ctx.content_hash)
    assert len(set(hashes)) == len(hashes)
