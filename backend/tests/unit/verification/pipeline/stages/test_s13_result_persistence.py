"""S13: store the automated result once, hand it to expert review, notify the
submitter once, and cache a pointer only for a settled result."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import func, select

from app.core.constants import (
    VERIFICATION_PIPELINE_VERSION,
    ContentStatus,
    OverallVerdict,
    SourceStatus,
    SubmissionStatus,
    SubmissionType,
)
from app.core.exceptions import PersistenceError
from app.features.auth.models import User
from app.features.notifications.models import Notification
from app.features.submissions.models import RetrievedArticle, SourceEvidenceQuery, Submission
from app.features.submissions.repository import RetrievedArticleRepository, SubmissionRepository
from app.features.verification.models import VerificationResult
from app.features.verification.pipeline.stages.s13_result_persistence import ResultPersistenceStage
from app.features.verification.repository import ResultRepository
from app.shared.utils.hashing import compute_url_hash
from tests.helpers.db import add_completed_submission, add_user
from tests.helpers.pipeline import article, make_context, run_analysis

HEADLINE = "প্রধান উপদেষ্টা ঢাকায় নতুন সেতুর উদ্বোধন করেছেন"
OTHER_URL = "https://prothomalo.com/article/2"
BODY = HEADLINE + "। অনুষ্ঠানে বহু মানুষ উপস্থিত ছিলেন এবং সেতুটিকে স্বাগত জানিয়েছেন।"


def cache() -> MagicMock:
    return MagicMock(set_claim_pointer=AsyncMock())


async def persist(session, *, submission_id=None, submitter_id=None, c=None, search_adequate=True, top=True):
    articles = [article(HEADLINE, BODY), article("অন্য খবর", url=OTHER_URL)] if top else []
    ctx = make_context(HEADLINE, articles=articles, search_adequate=search_adequate)
    ctx.content_hash, ctx.submission_id, ctx.submitter_id = "hash", submission_id, submitter_id
    ctx.search_queries = [("site:prothomalo.com " + HEADLINE, "headline")]
    ctx = await run_analysis(ctx)
    stage = ResultPersistenceStage(SubmissionRepository(session), ResultRepository(session),
                                   RetrievedArticleRepository(session), c or cache(), session=session)
    return await stage.execute(ctx)


async def count(session, model, *where) -> int:
    return (await session.execute(select(func.count()).select_from(model).where(*where))).scalar_one()


async def test_a_new_claim_is_stored_completely_and_enters_expert_review(session):
    user = await add_user(session, total_submissions=0)
    c = cache()
    out = await persist(session, submitter_id=user.id, c=c)
    sub = await session.get(Submission, out.submission_id)
    assert (sub.status, sub.processing_phase, sub.submitter_id) == (SubmissionStatus.EXPERT_REVIEW, "DONE", user.id)
    assert (await session.get(User, user.id)).total_submissions == 1

    res = await ResultRepository(session).get_by_submission_id(sub.id)
    assert (res.source_status, res.content_status, res.headline_check_status) == (
        SourceStatus.CONFIRMED, ContentStatus.MATCHED, "COMPLETED",
    )
    assert res.overall_verdict is None and res.ai_consensus_label is None  # no automated truth vote
    assert res.headline_exact_match is True and res.body_comparison_status == "SKIPPED"
    assert res.claim_scope == "HEADLINE_ONLY" and res.pipeline_version == VERIFICATION_PIPELINE_VERSION
    assert res.headline_keyword_coverage == 1.0 and res.analysis_details["headline_alteration"]["source_title"] == HEADLINE

    selected = (await session.execute(select(RetrievedArticle).where(RetrievedArticle.id == res.top_article_id))).scalar_one()
    assert selected.url == "https://prothomalo.com/article/1"
    assert await count(session, RetrievedArticle) == 2 and await count(session, SourceEvidenceQuery) == 1
    assert await count(session, Notification, Notification.user_id == user.id) == 1
    assert json.loads(c.set_claim_pointer.await_args.args[1])["submission_id"] == str(sub.id)


async def test_a_retry_is_idempotent_and_never_notifies_twice(session):
    owner = await add_user(session)
    sub = Submission(submission_type=SubmissionType.SOURCE_BASED, headline=HEADLINE, submitter_id=owner.id,
                     content_hash="x", status=SubmissionStatus.PENDING)
    session.add(sub)
    await session.flush()
    first = await persist(session, submission_id=sub.id)
    again = await persist(session, submission_id=sub.id)
    assert first.submission_id == again.submission_id == sub.id and again.persisted
    assert await count(session, VerificationResult) == 1
    assert await count(session, Notification) == 1


async def test_a_reviewed_submission_is_never_overwritten(session):
    sub, res = await add_completed_submission(session, headline=HEADLINE, submitter_id=None)
    res.overall_verdict, sub.status = OverallVerdict.REAL, SubmissionStatus.FINALIZED
    await session.flush()
    snapshot = (res.headline_similarity, res.reasoning)
    assert (await persist(session, submission_id=sub.id)).submission_id == sub.id
    after = await ResultRepository(session).get_by_submission_id(sub.id)
    assert (after.headline_similarity, after.reasoning, after.overall_verdict) == (*snapshot, OverallVerdict.REAL)


async def test_an_incomplete_result_is_stored_for_review_but_never_cached(session):
    c = cache()
    out = await persist(session, c=c, search_adequate=False, top=False)
    assert out.persisted and out.source_status == SourceStatus.INCOMPLETE
    c.set_claim_pointer.assert_not_awaited()


async def test_an_article_that_failed_extraction_before_is_completed_on_a_retry(session):
    sub = Submission(submission_type=SubmissionType.SOURCE_BASED, headline=HEADLINE, content_hash="x",
                     status=SubmissionStatus.PROCESSING)
    session.add(sub)
    await session.flush()
    session.add(RetrievedArticle(submission_id=sub.id, url="https://prothomalo.com/article/1",
                                 url_hash=compute_url_hash("https://prothomalo.com/article/1"),
                                 extraction_success=False))
    await session.flush()
    out = await persist(session, submission_id=sub.id)
    stored = (await session.execute(select(RetrievedArticle).where(RetrievedArticle.submission_id == sub.id,
                                                                   RetrievedArticle.url != OTHER_URL))).scalar_one()
    assert stored.extraction_success and stored.title == HEADLINE
    assert (await ResultRepository(session).get_by_submission_id(out.submission_id)).top_article_id == stored.id


async def test_a_storage_failure_is_a_persistence_error(session):
    ctx = await run_analysis(make_context(HEADLINE))
    repo = MagicMock(get_by_id_or_none=AsyncMock(side_effect=RuntimeError("db down")), session=session)
    with pytest.raises(PersistenceError):
        await ResultPersistenceStage(repo, MagicMock(), MagicMock(), cache(), session=session).execute(ctx)
