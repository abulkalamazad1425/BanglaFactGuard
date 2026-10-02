"""
tests/unit/test_source_resolution_guard.py
============================================
Business rule: "An unresolved source must not silently trigger unrestricted
search. Return an explicit source-resolution problem through the existing
API conventions."

Found bug: s04_source_search.py's domain filter only applies `if domain:` —
an unresolved claimed_source (normalized_source=None) previously let EVERY
candidate from EVERY provider through with no domain boundary at all, i.e.
genuinely unrestricted web search. s01_normalizer.py also only logged a
warning and continued rather than failing.

Covers:
- resolve_claimed_source() resolves via URL/domain, static alias, and DB
  registry, in that order, returning None only when all three miss.
- VerificationService.verify() / register_claim() and PhotoCardService.verify()
  all raise SourceNotFoundError BEFORE any Submission row is created or any
  pipeline/search work begins, when the claimed source can't be resolved.
- s01_normalizer.py's own defense-in-depth: if an unresolved source somehow
  reaches the pipeline anyway, it raises rather than silently continuing with
  normalized_source=None (which would have disabled S04's domain filter).
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import NormalizationError, SourceNotFoundError
from app.features.photocard.service import PhotoCardService
from app.features.sources.resolution import resolve_claimed_source
from app.features.verification.pipeline.context import build_context
from app.features.verification.pipeline.stages.s01_normalizer import InputNormalizerStage
from app.features.verification.schemas import VerificationRequest
from app.features.verification.service import VerificationService


# ─── resolve_claimed_source ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_resolves_via_url_extraction_without_touching_the_repo():
    repo = AsyncMock()
    canonical = await resolve_claimed_source("https://www.prothomalo.com/some/path", repo)
    assert canonical == "prothomalo.com"
    repo.resolve_source.assert_not_awaited()


@pytest.mark.asyncio
async def test_falls_back_to_db_registry_when_not_a_url_or_known_alias():
    repo = AsyncMock()
    repo.resolve_source.return_value = MagicMock(canonical_name="example-news.com")
    canonical = await resolve_claimed_source("এক্সাম্পল নিউজ", repo)
    assert canonical == "example-news.com"
    repo.resolve_source.assert_awaited_once()


@pytest.mark.asyncio
async def test_returns_none_when_every_strategy_misses():
    repo = AsyncMock()
    repo.resolve_source.return_value = None
    canonical = await resolve_claimed_source("কোনো অজানা পত্রিকা", repo)
    assert canonical is None


@pytest.mark.asyncio
async def test_returns_none_for_empty_input_without_calling_the_repo():
    repo = AsyncMock()
    canonical = await resolve_claimed_source("", repo)
    assert canonical is None
    repo.resolve_source.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_repo_lookup_failure_is_treated_as_unresolved_not_raised():
    repo = AsyncMock()
    repo.resolve_source.side_effect = RuntimeError("db unreachable")
    canonical = await resolve_claimed_source("কোনো পত্রিকা", repo)
    assert canonical is None


# ─── VerificationService — fails fast, before any work begins ──────────


def _request(source: str = "কোনো অজানা পত্রিকা") -> VerificationRequest:
    return VerificationRequest(
        headline="একটি শিরোনাম যথেষ্ট দীর্ঘ",
        claimed_source_text=source,
        body_text=None,
        published_date=None,
    )


@pytest.mark.asyncio
async def test_verify_raises_source_not_found_before_building_any_context():
    svc = VerificationService.__new__(VerificationService)
    svc.source_repo = AsyncMock()
    svc.source_repo.resolve_source.return_value = None

    with pytest.raises(SourceNotFoundError) as exc_info:
        await svc.verify(_request())
    assert exc_info.value.claimed_source == "কোনো অজানা পত্রিকা"


@pytest.mark.asyncio
async def test_register_claim_raises_source_not_found_before_creating_a_submission():
    svc = VerificationService.__new__(VerificationService)
    svc.source_repo = AsyncMock()
    svc.source_repo.resolve_source.return_value = None
    svc.submission_repo = AsyncMock()

    with pytest.raises(SourceNotFoundError):
        await svc.register_claim(_request())

    svc.submission_repo.create.assert_not_awaited()
    svc.submission_repo.get_verified_by_content_hash.assert_not_awaited()


@pytest.mark.asyncio
async def test_register_claim_proceeds_normally_when_source_resolves():
    svc = VerificationService.__new__(VerificationService)
    svc.source_repo = AsyncMock()
    svc.source_repo.resolve_source.return_value = None  # irrelevant: URL extraction wins first
    svc.submission_repo = AsyncMock()
    svc.submission_repo.get_verified_by_content_hash.return_value = None
    svc.submission_repo.get_in_flight_by_content_hash.return_value = None
    svc.reuse = MagicMock(find_reusable=AsyncMock(return_value=None))
    created = MagicMock(id=uuid.uuid4())
    svc.submission_repo.create.return_value = created
    svc.submission_repo.session = AsyncMock()

    request = _request(source="https://prothomalo.com")
    submission_id, status, cached = await svc.register_claim(request)

    svc.submission_repo.create.assert_awaited_once()
    assert submission_id == created.id


# ─── PhotoCardService.verify() — same guard ─────────────────────────────


@pytest.mark.asyncio
async def test_photocard_verify_raises_source_not_found_before_running_ocr():
    svc = PhotoCardService.__new__(PhotoCardService)
    svc.submission_repo = AsyncMock()
    svc.ocr_repo = AsyncMock()
    svc.source_repo = AsyncMock()
    svc.source_repo.resolve_source.return_value = None
    svc.ocr_service = AsyncMock()

    with pytest.raises(SourceNotFoundError):
        await svc.verify(
            image_bytes=b"fake-image-bytes",
            original_filename="card.jpg",
            claimed_source_text="কোনো অজানা পত্রিকা",
            published_date=None,
        )

    svc.ocr_service.recognize.assert_not_awaited()

    svc.submission_repo.update.assert_not_awaited()


# ─── s01_normalizer.py — defense-in-depth backstop ──────────────────────


@pytest.mark.asyncio
async def test_s01_raises_rather_than_silently_disabling_the_domain_filter():
    """If an unresolved source somehow reaches S01 anyway (the pre-checks
    above bypassed), it must fail the stage rather than leave
    normalized_source=None — which would have disabled S04's `if domain:`
    guard and searched the entire web unrestricted."""
    source_repo = AsyncMock()
    source_repo.resolve_source.return_value = None
    stage = InputNormalizerStage(source_repo=source_repo)

    context = build_context(headline="একটি শিরোনাম", claimed_source="কোনো অজানা পত্রিকা")

    with pytest.raises(NormalizationError):
        await stage.execute(context)

    assert context.normalized_source is None
