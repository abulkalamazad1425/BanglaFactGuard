"""
tests/unit/test_no_automated_overall_verdict.py
=================================================
Business rule: the automated system never decides an Overall verdict
(Fake/Real/Misleading/Altered) for SOURCE_BASED or PHOTO_CARD claims — it only
ever produces the three structured checks (source_status/content_status/
date_status). Overall is exclusively an expert-review outcome for these two
types, with no AI-implied default.

Covers:
- VerificationResponse.overall_verdict is always None before expert
  finalization, across every code path that builds one (fresh pipeline run,
  cache hit, and the stored-result read path for both source-based and
  photo-card claims).
- The expert consensus engine's Overall tally never tie-breaks toward an
  AI-implied value for SOURCE_BASED/PHOTO_CARD claims (there is no such
  value), even when the AI's own source_status would otherwise suggest one.
"""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.constants import ContentStatus, DateStatus, OverallVerdict, SourceStatus, SubmissionType
from app.features.submissions.models import Submission
from app.features.verification.models import VerificationResult
from app.features.verification.presenter import load_verification_response

from tests.unit.test_expert_review_finalize import _config, _make_service, _result, _review, _submission


async def _present(*, submission_type, source, content, date_, reused_from=None):
    sub = Submission(
        id=uuid.uuid4(), submission_type=submission_type, headline="হেডলাইন",
        claimed_source_text="প্রথম আলো", content_hash="h",
    )
    result = VerificationResult(
        id=uuid.uuid4(), submission_id=sub.id, source_status=source, content_status=content,
        date_status=date_, confidence=0.9, reasoning="", reused_from_submission_id=reused_from,
        created_at=datetime.now(timezone.utc),
    )
    result_repo = MagicMock(get_by_submission_id=AsyncMock(return_value=result))
    article_repo = MagicMock(get_for_submission=AsyncMock(return_value=[]))
    return await load_verification_response(sub, result_repo=result_repo, article_repo=article_repo)


# ─── The one read path (text claims, photo cards, reused results) ───────


@pytest.mark.asyncio
@pytest.mark.parametrize("submission_type", [SubmissionType.SOURCE_BASED, SubmissionType.PHOTO_CARD])
@pytest.mark.parametrize(
    "source,content,date_",
    [
        (SourceStatus.CONFIRMED, ContentStatus.MATCHED, DateStatus.MATCHED),
        (SourceStatus.CONFIRMED, ContentStatus.ALTERED, DateStatus.MISMATCHED),
        (SourceStatus.NOT_FOUND, None, None),
        (SourceStatus.INCOMPLETE, None, None),
    ],
)
async def test_stored_result_never_carries_overall_verdict_before_finalization(
    submission_type, source, content, date_
):
    response = await _present(submission_type=submission_type, source=source, content=content, date_=date_)
    assert response.overall_verdict is None
    assert response.is_finalized is False
    assert response.review_pending is True


@pytest.mark.asyncio
async def test_reused_result_never_carries_overall_verdict_either():
    response = await _present(
        submission_type=SubmissionType.PHOTO_CARD,
        source=SourceStatus.CONFIRMED, content=ContentStatus.MATCHED, date_=None,
        reused_from=uuid.uuid4(),
    )
    # the original is not (mock) finalized: expert state is read through, not copied
    assert response.cached is True
    assert response.overall_verdict is None and response.is_finalized is False


def test_persistence_stage_does_not_import_legacy_consensus_projection():
    import app.features.verification.pipeline.stages.s13_result_persistence as s13
    import app.features.verification.verdict_compat as compat

    assert "derive_expert_verdict" not in vars(s13)
    assert not hasattr(compat, "derive_expert_verdict")


# ─── Expert consensus: no AI tie-break for Overall on structured types ──


@pytest.mark.asyncio
async def test_structured_overall_tie_does_not_resolve_toward_ai_implied_fake():
    """Two experts split exactly evenly between FAKE and REAL on Overall for a
    SOURCE_BASED claim whose AI call is source=NOT_FOUND (which, under the old
    derive_ai_overall_verdict logic, implied FAKE). The business rule is that
    Overall has no automated default — the tie must NOT resolve toward FAKE;
    it must simply fail to finalize on Overall."""
    ctx = _make_service()
    submission = _submission(SubmissionType.SOURCE_BASED)
    config = _config(T=1.0, M=1, margin=0.5)
    ctx["voting_config"].get_or_create.return_value = config
    # AI says NOT_FOUND — under the old (removed) logic this implied Overall=FAKE.
    result = _result(SourceStatus.NOT_FOUND, None, None, confidence=0.95)
    ctx["results"].get_by_submission_id.return_value = result

    reviews = [
        _review(OverallVerdict.FAKE, 1.0, source=SourceStatus.NOT_FOUND),
        _review(OverallVerdict.REAL, 1.0, source=SourceStatus.NOT_FOUND),
    ]
    ctx["reviews"].get_for_submission.return_value = reviews

    await ctx["svc"]._finalize_or_escalate(submission)

    # Source itself finalizes fine (both experts agree NOT_FOUND, AI agrees too)
    # but Overall is tied 1.0/1.0 with no tie-break -> margin check fails ->
    # the claim as a whole does not finalize.
    ctx["results"].update.assert_not_awaited()
    ctx["submissions"].mark_finalized.assert_not_awaited()


@pytest.mark.asyncio
async def test_structured_overall_vote_snapshot_has_no_ai_implied_value():
    """ExpertReview.ai_overall_verdict is NULL for SOURCE_BASED/PHOTO_CARD
    votes — there is nothing to snapshot since the automated system never
    computes an Overall verdict for these types."""
    ctx = _make_service()
    expert_id = uuid.uuid4()
    submission = _submission(SubmissionType.PHOTO_CARD)
    ctx["submissions"].get_by_id_locked.return_value = submission
    ctx["reviews"].get_by_submission_and_reviewer.return_value = None

    created: list = []

    def _capture_create(review):
        review.created_at = review.created_at or datetime.now(timezone.utc)
        review.updated_at = review.updated_at or datetime.now(timezone.utc)
        created.append(review)
        return review

    ctx["reviews"].create.side_effect = _capture_create
    ctx["voting_config"].get_or_create.return_value = _config()
    ctx["profiles"].get_or_create.return_value = SimpleNamespace(total_votes=0, correct_votes=0)
    ctx["results"].get_by_submission_id.return_value = _result(
        SourceStatus.CONFIRMED, ContentStatus.MATCHED, DateStatus.MATCHED
    )
    ctx["reviews"].get_for_submission.return_value = []

    await ctx["svc"].submit_vote(
        submission_id=submission.id,
        expert_id=expert_id,
        overall_verdict=OverallVerdict.REAL,
        source_status=SourceStatus.CONFIRMED,
        content_status=ContentStatus.MATCHED,
        date_status=DateStatus.MATCHED,
        justification="x" * 60,
    )

    assert len(created) == 1
    assert created[0].ai_overall_verdict is None


# ─── legacy rows obey claim scope on read ───────────────────────────────


@pytest.mark.asyncio
async def test_historical_photocard_row_never_exposes_an_old_content_verdict():
    sub = Submission(
        id=uuid.uuid4(), submission_type=SubmissionType.PHOTO_CARD, headline="হেডলাইন",
        claimed_source_text="প্রথম আলো", content_hash="h",
    )
    # a row written by the old code: content verdict, no headline status/scope/version
    result = VerificationResult(
        id=uuid.uuid4(), submission_id=sub.id, source_status=SourceStatus.CONFIRMED,
        content_status=ContentStatus.ALTERED, confidence=0.5, reasoning="",
        analysis_details={"metrics": {}, "passages": [], "body_similarity_scores": {"available": True}},
        created_at=datetime.now(timezone.utc),
    )
    response = await load_verification_response(
        sub,
        result_repo=MagicMock(get_by_submission_id=AsyncMock(return_value=result)),
        article_repo=MagicMock(get_for_submission=AsyncMock(return_value=[])),
    )
    assert response.claim_scope.value == "HEADLINE_ONLY"
    assert response.legacy_result is True
    assert response.content_status is None and response.ai_content_status is None
    assert response.analysis.body_similarity is None and response.analysis.headline_alteration is None
    assert response.pipeline_version is None
