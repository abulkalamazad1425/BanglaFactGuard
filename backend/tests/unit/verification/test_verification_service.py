"""Claim registration and verification: a checked claim is never re-run,
every requester gets their own submission, and an unresolved source never
runs an unrestricted search."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import delete, func, select

from app.core.constants import ClaimScope, PipelineStageID, SourceStatus, SubmissionStatus
from app.core.exceptions import SourceNotFoundError
from app.features.notifications.models import Notification
from app.features.sources.repository import SourceRepository
from app.features.submissions.models import Submission
from app.features.submissions.repository import RetrievedArticleRepository, SubmissionRepository
from app.features.verification import source_policy
from app.features.verification.job_repository import VerificationJobRepository
from app.features.verification.models import VerificationJob, VerificationResult
from app.features.verification.pipeline.stages.s01_normalizer import InputNormalizerStage
from app.features.verification.pipeline.stages.s02_cache_lookup import CacheLookupStage
from app.features.verification.pipeline.stages.s13_result_persistence import ResultPersistenceStage
from app.features.verification.repository import ResultRepository
from app.features.verification.schemas import VerificationRequest
from app.features.verification.service import VerificationService
from app.shared.utils.hashing import compute_claim_hash
from tests.helpers.db import add_completed_submission, add_source, add_user
from tests.helpers.pipeline import article, run_analysis

HEADLINE = "প্রধান উপদেষ্টা ঢাকায় নতুন সেতুর উদ্বোধন করেছেন"


class Analysis:
    """S03-S12 stand-in: the claimed outlet carries the exact report."""

    stage_id = PipelineStageID.S08_SOURCE_CORRESPONDENCE

    async def execute(self, ctx):
        top = article(HEADLINE, HEADLINE + "। " + "অনুষ্ঠানে বহু মানুষ উপস্থিত ছিলেন। " * 3)
        ctx.ranked_articles = ctx.extracted_articles = [top]
        ctx.top_article = top
        ctx.search_attempted = ctx.search_success = 2
        ctx.search_adequate = True
        return await run_analysis(ctx)


def pointer_cache() -> MagicMock:
    store: dict = {}
    c = MagicMock(get_claim_result=AsyncMock(side_effect=lambda k: store.get(k)), invalidate_claim=AsyncMock())
    c.set_claim_pointer = AsyncMock(side_effect=lambda k, payload, ttl: store.__setitem__(k, payload.encode()))
    return c


def service(session, cache=None) -> VerificationService:
    cache = cache or pointer_cache()
    svc = VerificationService(SubmissionRepository(session), ResultRepository(session), RetrievedArticleRepository(session),
                              SourceRepository(session), cache, MagicMock(), MagicMock(), MagicMock(), MagicMock())
    svc._build_stages = lambda: [
        InputNormalizerStage(svc.source_repo),
        CacheLookupStage(cache, svc.submission_repo, svc.result_repo),
        Analysis(),
        ResultPersistenceStage(svc.submission_repo, svc.result_repo, svc.article_repo, cache, session=session),
    ]
    return svc


def req(**kw) -> VerificationRequest:
    return VerificationRequest(**{"headline": HEADLINE, "claimed_source_text": "প্রথম আলো", **kw})


async def jobs(session) -> int:
    return (await session.execute(select(func.count()).select_from(VerificationJob))).scalar_one()


@pytest.fixture
async def session(session):
    await add_source(session)
    await session.commit()
    return session


# ── synchronous verification ─────────────────────────────────────────────

async def test_a_claim_is_verified_once_and_each_requester_gets_their_own_copy(session):
    owner, other = await add_user(session), await add_user(session)
    svc = service(session)
    first = await svc.verify(req(published_date=date(2026, 6, 7)), submitter_id=owner.id)
    assert first.cached is False and first.source_status == SourceStatus.CONFIRMED and first.overall_verdict is None
    assert first.processing_time_ms is not None and not first.analysis.timings.cache_hit
    assert {"s01_normalizer", "s02_cache_lookup", "s13_result_persistence"} <= set(first.analysis.timings.stage_ms)

    second = await svc.verify(req(published_date=date(2026, 6, 7)), submitter_id=other.id)
    assert second.cached and second.analysis.timings.cache_hit
    assert set(second.analysis.timings.stage_ms) == {"s01_normalizer", "s02_cache_lookup"}  # nothing re-ran
    mine = await SubmissionRepository(session).get_by_id(second.submission_id)
    assert (mine.submitter_id, mine.duplicate_of_submission_id) == (other.id, first.submission_id)
    for key in ("source_status", "content_status", "headline_check_status", "claim_scope"):
        assert getattr(first, key) == getattr(second, key)
    assert (await svc.get_result(second.submission_id)).model_dump() == second.model_dump()
    assert await svc.get_result(owner.id) is None


async def test_a_queued_submission_is_verified_from_its_stored_row(session):
    owner = await add_user(session)
    svc = service(session)
    await svc.verify(req(), submitter_id=None)  # an earlier identical claim
    sid, *_ = await svc.register_claim(req(body_text="ভিন্ন বডি"), submitter_id=owner.id)
    queued = await SubmissionRepository(session).get_by_id(sid)
    queued.body_text = None  # now identical to the earlier claim
    response = await svc.run_for_submission(sid)
    assert response.submission_id == sid and response.cached  # the queued row itself carries the copy
    notes = (await session.execute(select(Notification).where(Notification.user_id == owner.id))).scalars().all()
    assert [n.link_url for n in notes] == [f"/verify/{sid}"]


# ── asynchronous registration ────────────────────────────────────────────

async def test_registration_commits_the_submission_and_its_job_with_the_pipeline_identity(db, session):
    sid, status, cached = await service(session).register_claim(req(body_text="বডি  টেক্সট", published_date=date(2026, 6, 7)))
    assert (status, cached) == (SubmissionStatus.PENDING, False)
    async with db() as fresh:  # committed: a new session sees both rows
        sub = await SubmissionRepository(fresh).get_by_id(sid)
        job = await VerificationJobRepository(fresh).get_by_submission(sid)
    assert (sub.processing_phase, job.status, job.kind) == ("QUEUED", "QUEUED", "SOURCE_BASED")
    assert sub.content_hash == compute_claim_hash(HEADLINE, "prothomalo.com", ClaimScope.HEADLINE_WITH_BODY,
                                                  body="বডি টেক্সট", published_date=date(2026, 6, 7))


async def test_identical_claims_collapse_only_when_everything_matches(session):
    user = await add_user(session)
    svc = service(session)
    a, *_ = await svc.register_claim(req(published_date=date(2026, 6, 7)), submitter_id=user.id)
    again, *_ = await svc.register_claim(req(published_date=date(2026, 6, 7)), submitter_id=user.id)
    b, *_ = await svc.register_claim(req(published_date=date(2026, 6, 8)), submitter_id=user.id)
    c, *_ = await svc.register_claim(req(body_text="অন্য বডি"), submitter_id=user.id)
    assert a == again and len({a, b, c}) == 3 and await jobs(session) == 3


async def test_a_checked_claim_is_copied_for_a_new_requester_and_never_queued(session):
    owner, other = await add_user(session), await add_user(session)
    orig, _ = await add_completed_submission(session, headline=HEADLINE, submitter_id=owner.id)
    await session.commit()
    svc = service(session)
    assert await svc.register_claim(req(), submitter_id=owner.id) == (orig.id, SubmissionStatus.EXPERT_REVIEW, True)
    sid, status, cached = await svc.register_claim(req(), submitter_id=other.id)
    assert (cached, status) == (True, SubmissionStatus.EXPERT_REVIEW) and sid != orig.id
    copy = await ResultRepository(session).get_by_submission_id(sid)
    assert copy.reused_from_submission_id == orig.id and await jobs(session) == 0
    assert (await session.execute(select(func.count()).select_from(Notification)
                                  .where(Notification.user_id == other.id))).scalar_one() == 1


@pytest.mark.parametrize("prior", ["incomplete", "deleted"])
async def test_an_unsettled_or_deleted_result_is_verified_afresh(session, prior):
    owner, other = await add_user(session), await add_user(session)
    orig, _ = await add_completed_submission(
        session, headline=HEADLINE, submitter_id=owner.id,
        source_status=SourceStatus.INCOMPLETE if prior == "incomplete" else SourceStatus.CONFIRMED,
    )
    if prior == "deleted":  # Postgres cascades; emulated on SQLite
        await session.execute(delete(VerificationResult).where(VerificationResult.submission_id == orig.id))
        await session.execute(delete(Submission).where(Submission.id == orig.id))
    await session.commit()
    sid, status, cached = await service(session).register_claim(req(), submitter_id=other.id)
    assert (cached, status) == (False, SubmissionStatus.PENDING) and sid != orig.id and await jobs(session) == 1


async def test_a_missing_source_is_queued_for_verified_sources_and_rejected_when_that_is_off(session, monkeypatch):
    svc = service(session)
    sid, status, _ = await svc.register_claim(req(claimed_source_text=None))
    sub = await SubmissionRepository(session).get_by_id(sid)
    scope = await source_policy.load_verified_scope(svc.source_repo)
    assert status == SubmissionStatus.PENDING and sub.claimed_source_text is None
    assert sub.content_hash == compute_claim_hash(HEADLINE, source_policy.verified_identity_key(scope), ClaimScope.HEADLINE_ONLY)

    monkeypatch.setattr(source_policy, "fallback_enabled", lambda: False)
    for call in (svc.register_claim(req(claimed_source_text="অজানা পত্রিকা")),
                 svc.verify(req(claimed_source_text="অজানা পত্রিকা"))):
        with pytest.raises(SourceNotFoundError):
            await call
    assert (await session.execute(select(func.count()).select_from(Submission))).scalar_one() == 1
