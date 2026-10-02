"""
tests/unit/test_incomplete_never_cached.py
==========================================
A run that ends INCOMPLETE (the automated check itself failed or could not
finish) still reaches expert review so experts see the indicator — but no
reader of stored results may treat it as a settled answer.

Covers (against a real SQLite database):
- S02's database path and Redis path never hit on an INCOMPLETE result.
- S12 never writes the Redis pointer for an INCOMPLETE result, and does for a
  complete one.
- register_claim does not hand back an INCOMPLETE result as "already
  verified" - it queues a fresh run.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.constants import ContentStatus, SourceStatus, VERIFICATION_PIPELINE_VERSION
from app.features.sources.repository import SourceRepository
from app.features.submissions.repository import RetrievedArticleV2Repository, SubmissionRepository
from app.features.verification.pipeline.stages.s02_cache_lookup import CacheLookupStage
from app.features.verification.pipeline.stages.s12_persistence import PersistenceStage
from app.features.verification.repository import ResultV2Repository
from app.features.verification.schemas import VerificationRequest
from app.features.verification.service import VerificationService
from app.shared.utils.hashing import compute_claim_hash
from db_helpers import add_completed_submission, add_source, add_user, make_session_factory
from pipeline_helpers import article, make_context, run_analysis

HEADLINE = "সরকার নতুন সেতু উদ্বোধন করেছে"


@pytest.fixture
async def db():
    engine, factory = await make_session_factory()
    async with factory() as s:
        await add_source(s)
        await s.commit()
    yield factory
    await engine.dispose()


def _cache(pointer=None):
    c = MagicMock()
    c.get_claim_result = AsyncMock(return_value=json.dumps(pointer).encode() if pointer else None)
    c.set_claim_pointer = AsyncMock()
    c.invalidate_claim = AsyncMock()
    return c


async def test_s02_never_hits_on_incomplete_via_db_or_redis(db):
    async with db() as s:
        u = await add_user(s)
        sub, _ = await add_completed_submission(s, headline=HEADLINE, submitter_id=u.id, source_status=SourceStatus.INCOMPLETE)
        await s.commit()
        for cache in (_cache(), _cache({"submission_id": str(sub.id), "pipeline_version": VERIFICATION_PIPELINE_VERSION})):
            ctx = make_context(HEADLINE)
            ctx.content_hash = sub.content_hash
            out = await CacheLookupStage(cache, SubmissionRepository(s), ResultV2Repository(s)).execute(ctx)
            assert out.cache_hit is False


async def test_s02_hits_on_a_complete_result(db):
    async with db() as s:
        u = await add_user(s)
        sub, _ = await add_completed_submission(s, headline=HEADLINE, submitter_id=u.id)
        await s.commit()
        cache = _cache()
        ctx = make_context(HEADLINE)
        ctx.content_hash = sub.content_hash
        out = await CacheLookupStage(cache, SubmissionRepository(s), ResultV2Repository(s)).execute(ctx)
        assert out.cache_hit and out.reused_from_submission_id == sub.id
        cache.set_claim_pointer.assert_awaited_once()  # DB hit is written back to Redis


async def _run_s12(s, cache, *, top):
    ctx = make_context(HEADLINE, top=top, search_adequate=top is not None)
    ctx.content_hash = compute_claim_hash(HEADLINE, "prothomalo.com", ctx.claim_scope)
    ctx = await run_analysis(ctx)
    stage = PersistenceStage(SubmissionRepository(s), ResultV2Repository(s), RetrievedArticleV2Repository(s), cache, session=s)
    return ctx, await stage.execute(ctx)


async def test_s12_skips_the_redis_pointer_for_an_incomplete_result(db):
    async with db() as s:
        cache = _cache()
        # no article + inadequate search => Source INCOMPLETE
        ctx = make_context(HEADLINE, search_adequate=False)
        ctx.content_hash = "h"
        from pipeline_helpers import run_analysis as ra

        ctx = await ra(ctx)
        assert ctx.source_status == SourceStatus.INCOMPLETE
        out = await PersistenceStage(
            SubmissionRepository(s), ResultV2Repository(s), RetrievedArticleV2Repository(s), cache, session=s
        ).execute(ctx)
        assert out.persisted
        cache.set_claim_pointer.assert_not_awaited()


async def test_s12_writes_the_redis_pointer_for_a_complete_result(db):
    async with db() as s:
        cache = _cache()
        ctx, out = await _run_s12(s, cache, top=article(HEADLINE, HEADLINE + "।"))
        assert ctx.content_status == ContentStatus.MATCHED
        cache.set_claim_pointer.assert_awaited_once()
        assert json.loads(cache.set_claim_pointer.await_args.args[1])["submission_id"] == str(out.submission_id)


async def test_register_claim_requeues_instead_of_serving_an_incomplete_result(db):
    async with db() as s:
        u = await add_user(s)
        prior, _ = await add_completed_submission(s, headline=HEADLINE, submitter_id=u.id, source_status=SourceStatus.INCOMPLETE)
        await s.commit()
        svc = VerificationService(
            SubmissionRepository(s), ResultV2Repository(s), RetrievedArticleV2Repository(s), SourceRepository(s),
            _cache(), MagicMock(), MagicMock(), MagicMock(), MagicMock(),
        )
        sid, status, cached = await svc.register_claim(
            VerificationRequest(headline=HEADLINE, claimed_source_text="প্রথম আলো"), submitter_id=u.id
        )
    assert cached is False and sid != prior.id and status.value == "PENDING"
