"""The single read path from the database to a VerificationResponse. The
automated system never shows an overall verdict; experts' final decision
does, and a reused copy follows its original live."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.constants import (
    ContentStatus,
    DateStatus,
    OverallVerdict,
    SourceStatus,
    SubmissionStatus,
    SubmissionType,
)
from app.features.expert_review.models import ExpertReview
from app.features.submissions.repository import RetrievedArticleRepository
from app.features.verification.presenter import effective_status, load_verification_response
from app.features.verification.repository import ResultRepository
from tests.helpers.db import add_completed_submission, add_user


async def present(session, sub):
    return await load_verification_response(
        sub, result_repo=ResultRepository(session), article_repo=RetrievedArticleRepository(session)
    )


@pytest.mark.parametrize("kind", [SubmissionType.SOURCE_BASED, SubmissionType.PHOTO_CARD])
@pytest.mark.parametrize("source,content,date_", [
    (SourceStatus.CONFIRMED, ContentStatus.MATCHED, DateStatus.MATCHED),
    (SourceStatus.CONFIRMED, ContentStatus.ALTERED, DateStatus.MISMATCHED),
    (SourceStatus.NOT_FOUND, None, None),
    (SourceStatus.INCOMPLETE, None, None),
])
async def test_a_preliminary_result_never_carries_an_overall_verdict(session, kind, source, content, date_):
    sub, _ = await add_completed_submission(session, headline="h", submitter_id=None, submission_type=kind,
                                            source_status=source, content_status=content, date_status=date_)
    r = await present(session, sub)
    assert (r.overall_verdict, r.is_finalized, r.review_pending) == (None, False, True)
    assert (r.source_status, r.content_status, r.date_status) == (source, content, date_)


async def test_a_final_decision_is_shown_beside_the_unchanged_ai_findings(session):
    admin = await add_user(session, role="admin")
    sub, res = await add_completed_submission(session, headline="h", submitter_id=None,
                                              overall_verdict=OverallVerdict.MISLEADING,
                                              final_content_status=ContentStatus.ALTERED)
    sub.status = SubmissionStatus.FINALIZED
    session.add(ExpertReview(submission_id=sub.id, reviewer_id=admin.id, vote_overall_verdict=OverallVerdict.MISLEADING,
                             credibility_weight=1.0, status="finalized", is_admin_decision=True))
    await session.flush()
    r = await present(session, sub)
    assert (r.overall_verdict, r.is_finalized, r.review_pending, r.decided_by_admin) == (
        OverallVerdict.MISLEADING, True, False, True,
    )
    assert r.content_status == r.ai_content_status == ContentStatus.MATCHED  # never replaced by a supplementary finding


async def test_a_reused_copy_follows_its_original_review_live(session):
    original, orig_res = await add_completed_submission(session, headline="h", submitter_id=None)
    copy, _ = await add_completed_submission(session, headline="h", submitter_id=None,
                                             reused_from_submission_id=original.id)
    copy.duplicate_of_submission_id = original.id
    await session.flush()
    r = await present(session, copy)
    assert r.cached and r.overall_verdict is None
    orig_res.overall_verdict = OverallVerdict.FAKE
    await session.flush()
    assert (await present(session, copy)).overall_verdict == OverallVerdict.FAKE
    assert effective_status(copy, SubmissionStatus.FINALIZED) == SubmissionStatus.FINALIZED
    assert effective_status(original, SubmissionStatus.FINALIZED) == SubmissionStatus.EXPERT_REVIEW


async def test_legacy_rows_never_expose_an_old_content_verdict_as_a_headline_verdict(session):
    legacy = {"pipeline_version": "v3.3", "headline_alteration": {"reason": "old", "kind": "none"},
              "metrics": {}, "body_similarity": {"status": "COMPUTED", "jaccard": {"available": True, "value": 0.5}}}
    sub, _ = await add_completed_submission(session, headline="h", submitter_id=None, body="বডি",
                                            submission_type=SubmissionType.PHOTO_CARD, pipeline_version="v3.3",
                                            content_status=ContentStatus.ALTERED, headline_check_status=None,
                                            analysis_details=legacy)
    r = await present(session, sub)
    assert r.legacy_result and r.content_status is None and r.ai_content_status is None and r.headline_status is None
    assert r.claim_scope.value == "HEADLINE_ONLY"  # a photo card is always headline-only
    assert r.analysis.headline_alteration is None and r.analysis.body_similarity.jaccard.value == 0.5


async def test_without_a_stored_result_there_is_no_response(session):
    sub, res = await add_completed_submission(session, headline="h", submitter_id=None)
    res.source_status = None
    assert await present(session, sub) is None


async def test_the_selected_article_comes_first_with_at_most_three_unique_articles():
    primary_id = uuid.uuid4()

    def art(url, rank, aid=None):
        return SimpleNamespace(id=aid or uuid.uuid4(), url=url, title=url, author=None, published_date=None, body="b",
                               rank_score=rank, extraction_method=None, extraction_success=True)

    articles = [art("https://www.jugantor.com/a", 0.9), art("https://www.jugantor.com/a/", 0.85),
                art("https://www.prothomalo.com/b", 0.8), art("https://www.prothomalo.com/c", 0.7),
                art("https://www.jugantor.com/primary", 0.4, primary_id)]
    result = SimpleNamespace(
        source_status=SourceStatus.CONFIRMED, content_status=ContentStatus.MATCHED, date_status=None,
        overall_verdict=None, reused_from_submission_id=None, top_article_id=primary_id, claim_scope="HEADLINE_ONLY",
        headline_check_status="COMPLETED", headline_exact_match=True, confidence=0.9, reasoning="r",
        avg_verification_time_ms=1, created_at="2026-01-01T00:00:00", pipeline_version="v", submission_id=None,
        analysis_details={"source_scope": {"verification_mode": "VERIFIED_SOURCES",
                                           "eligible_publishers": ["jugantor.com", "prothomalo.com"]}},
    )
    sub = SimpleNamespace(id=uuid.uuid4(), submission_type="SOURCE_BASED", body_text=None, headline="h",
                          published_date=None, claimed_source_text=None, duplicate_of_submission_id=None)
    r = await load_verification_response(
        sub, result_repo=MagicMock(get_by_submission_id=AsyncMock(return_value=result)),
        article_repo=MagicMock(get_for_submission=AsyncMock(return_value=articles)),
    )
    assert [a.url for a in r.matched_articles] == [
        "https://www.jugantor.com/primary", "https://www.jugantor.com/a", "https://www.prothomalo.com/b",
    ]
    assert [a.is_primary for a in r.matched_articles] == [True, False, False]
    assert [a.publisher for a in r.matched_articles] == ["jugantor.com", "jugantor.com", "prothomalo.com"]
    assert r.verification_mode == "VERIFIED_SOURCES"
