"""
tests/unit/test_expert_review_finalize.py
==========================================
Unit tests for the credibility-weighted expert consensus engine
(ExpertReviewService._finalize_submission / _pick_winner / _update_expert_profiles).

Every submission type (SOURCE_BASED, PHOTO_CARD, MULTIMODAL) votes on an
Overall verdict (Fake/Real/Misleading/Altered) — tallied independently of the
(Source, Content, Date) structured vote that additionally exists for
SOURCE_BASED/PHOTO_CARD claims only. Content/Date are only tallied when the
winning Source status is CONFIRMED. Each dimension's AI prior is weighted by
the AI's own confidence; ties favor the AI's call.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.constants import (
    ContentStatus,
    DateStatus,
    MultimodalPredictionLabel,
    OverallVerdict,
    SourceStatus,
    SubmissionType,
)
from app.features.expert_review.models import ExpertReviewV2
from app.features.expert_review.service import ExpertReviewService, _pick_winner
from app.features.multimodal.models import MultimodalAnalysis
from app.features.submissions.models import Submission
from app.features.verification.models import VerificationResultV2


def _make_service():
    review_repo = AsyncMock()
    profile_repo = AsyncMock()
    tier_repo = AsyncMock()
    submission_repo = AsyncMock()
    result_repo = AsyncMock()
    multimodal_repo = AsyncMock()
    voting_config_repo = AsyncMock()
    review_repo.session = MagicMock()
    svc = ExpertReviewService(
        review_repo=review_repo,
        profile_repo=profile_repo,
        tier_repo=tier_repo,
        submission_repo=submission_repo,
        result_repo=result_repo,
        multimodal_repo=multimodal_repo,
        voting_config_repo=voting_config_repo,
    )
    return svc, review_repo, profile_repo, submission_repo, result_repo, multimodal_repo


def _review(
    overall: OverallVerdict,
    weight: float,
    *,
    source: SourceStatus | None = None,
    content: ContentStatus | None = None,
    date_: DateStatus | None = None,
) -> ExpertReviewV2:
    return ExpertReviewV2(
        id=uuid.uuid4(),
        submission_id=uuid.uuid4(),
        reviewer_id=uuid.uuid4(),
        ai_overall_verdict=OverallVerdict.REAL,
        ai_source_status=SourceStatus.CONFIRMED,
        ai_content_status=ContentStatus.MATCHED,
        ai_date_status=DateStatus.MATCHED,
        vote_overall_verdict=overall,
        vote_source_status=source,
        vote_content_status=content,
        vote_date_status=date_,
        credibility_weight=weight,
        status="pending",
    )


def _result(source, content, date_, confidence) -> VerificationResultV2:
    return VerificationResultV2(
        id=uuid.uuid4(),
        submission_id=uuid.uuid4(),
        source_status=source,
        content_status=content,
        date_status=date_,
        confidence=confidence,
    )


def _submission(submission_type: SubmissionType) -> Submission:
    return Submission(id=uuid.uuid4(), submission_type=submission_type, content_hash="x")


def _multimodal_analysis(prediction, confidence_fake, confidence_real) -> MultimodalAnalysis:
    return MultimodalAnalysis(
        id=uuid.uuid4(),
        submission_id=uuid.uuid4(),
        image_object_key="k",
        prediction=prediction,
        confidence_fake=confidence_fake,
        confidence_real=confidence_real,
    )


# ─── _pick_winner (pure function) ──────────────────────────────────────


def test_pick_winner_clear_majority():
    weights = {SourceStatus.CONFIRMED: 3.0, SourceStatus.NOT_FOUND: 1.0}
    assert _pick_winner(weights, tie_break=SourceStatus.NOT_FOUND) == SourceStatus.CONFIRMED


def test_pick_winner_tie_favors_tie_break():
    weights = {SourceStatus.CONFIRMED: 2.0, SourceStatus.NOT_FOUND: 2.0}
    assert _pick_winner(weights, tie_break=SourceStatus.NOT_FOUND) == SourceStatus.NOT_FOUND
    assert _pick_winner(weights, tie_break=SourceStatus.CONFIRMED) == SourceStatus.CONFIRMED


def test_pick_winner_tie_with_none_tie_break_picks_a_winner():
    weights = {ContentStatus.MATCHED: 1.0, ContentStatus.ALTERED: 1.0}
    assert _pick_winner(weights, tie_break=None) in weights


# ─── _finalize_submission — SOURCE_BASED / PHOTO_CARD ──────────────────


@pytest.mark.asyncio
async def test_finalize_confirmed_majority_sets_content_date_and_overall():
    svc, review_repo, _profile_repo, submission_repo, result_repo, _mm_repo = _make_service()

    reviews = [
        _review(
            OverallVerdict.REAL,
            1.0,
            source=SourceStatus.CONFIRMED,
            content=ContentStatus.MATCHED,
            date_=DateStatus.MATCHED,
        )
        for _ in range(3)
    ]
    review_repo.get_for_submission.return_value = reviews
    submission_repo.get_by_id.return_value = _submission(SubmissionType.SOURCE_BASED)
    # AI disagreed on everything, but is outweighted 3-to-0.6 by experts.
    result = _result(SourceStatus.CONFIRMED, ContentStatus.ALTERED, DateStatus.MISMATCHED, 0.6)
    result_repo.get_by_submission_id.return_value = result

    await svc._finalize_submission(uuid.uuid4())

    result_repo.update.assert_awaited_once()
    _, kwargs = result_repo.update.call_args
    assert kwargs["source_status"] == SourceStatus.CONFIRMED
    assert kwargs["content_status"] == ContentStatus.MATCHED
    assert kwargs["date_status"] == DateStatus.MATCHED
    assert kwargs["overall_verdict"] == OverallVerdict.REAL
    submission_repo.mark_finalized.assert_awaited_once()
    assert review_repo.update.await_count == len(reviews)


@pytest.mark.asyncio
async def test_finalize_not_found_majority_leaves_content_and_date_null():
    svc, review_repo, _profile_repo, submission_repo, result_repo, _mm_repo = _make_service()

    reviews = [
        _review(OverallVerdict.FAKE, 1.0, source=SourceStatus.NOT_FOUND),
        _review(OverallVerdict.FAKE, 1.0, source=SourceStatus.NOT_FOUND),
    ]
    review_repo.get_for_submission.return_value = reviews
    submission_repo.get_by_id.return_value = _submission(SubmissionType.SOURCE_BASED)
    result = _result(SourceStatus.CONFIRMED, ContentStatus.MATCHED, DateStatus.MATCHED, 0.5)
    result_repo.get_by_submission_id.return_value = result

    await svc._finalize_submission(uuid.uuid4())

    _, kwargs = result_repo.update.call_args
    assert kwargs["source_status"] == SourceStatus.NOT_FOUND
    assert kwargs["content_status"] is None
    assert kwargs["date_status"] is None
    assert kwargs["overall_verdict"] == OverallVerdict.FAKE


@pytest.mark.asyncio
async def test_finalize_source_tie_favors_ai_call():
    svc, review_repo, _profile_repo, submission_repo, result_repo, _mm_repo = _make_service()

    reviews = [
        _review(
            OverallVerdict.REAL,
            1.0,
            source=SourceStatus.CONFIRMED,
            content=ContentStatus.MATCHED,
            date_=DateStatus.MATCHED,
        ),
        _review(OverallVerdict.FAKE, 1.0, source=SourceStatus.NOT_FOUND),
    ]
    review_repo.get_for_submission.return_value = reviews
    submission_repo.get_by_id.return_value = _submission(SubmissionType.PHOTO_CARD)
    result = _result(SourceStatus.CONFIRMED, ContentStatus.MATCHED, DateStatus.MATCHED, 0.0)
    result_repo.get_by_submission_id.return_value = result

    await svc._finalize_submission(uuid.uuid4())

    _, kwargs = result_repo.update.call_args
    assert kwargs["source_status"] == SourceStatus.CONFIRMED


@pytest.mark.asyncio
async def test_finalize_noop_when_no_reviews():
    svc, review_repo, _profile_repo, submission_repo, result_repo, _mm_repo = _make_service()
    review_repo.get_for_submission.return_value = []

    await svc._finalize_submission(uuid.uuid4())

    result_repo.update.assert_not_awaited()
    submission_repo.mark_finalized.assert_not_awaited()
    submission_repo.get_by_id.assert_not_awaited()


# ─── _finalize_submission — MULTIMODAL (Overall only, no sub-dimensions) ──


@pytest.mark.asyncio
async def test_finalize_multimodal_tallies_overall_only():
    svc, review_repo, _profile_repo, submission_repo, result_repo, mm_repo = _make_service()

    reviews = [
        _review(OverallVerdict.MISLEADING, 1.0),
        _review(OverallVerdict.MISLEADING, 1.0),
        _review(OverallVerdict.REAL, 1.0),
    ]
    review_repo.get_for_submission.return_value = reviews
    submission_repo.get_by_id.return_value = _submission(SubmissionType.MULTIMODAL)
    mm = _multimodal_analysis(MultimodalPredictionLabel.NON_FAKE, 0.1, 0.9)
    mm_repo.get_by_submission_id.return_value = mm

    await svc._finalize_submission(uuid.uuid4())

    mm_repo.update.assert_awaited_once()
    _, kwargs = mm_repo.update.call_args
    assert kwargs["expert_overall_verdict"] == OverallVerdict.MISLEADING
    # Multimodal has no source/content/date dimensions to write back.
    result_repo.update.assert_not_awaited()
    submission_repo.mark_finalized.assert_awaited_once()


# ─── _update_expert_profiles (correctness scoring) ─────────────────────


@pytest.mark.asyncio
async def test_update_expert_profiles_scores_on_overall_match():
    svc, _review_repo, profile_repo, _submission_repo, _result_repo, _mm_repo = _make_service()

    correct = _review(OverallVerdict.ALTERED, 1.0)
    wrong = _review(OverallVerdict.REAL, 1.0)

    profiles = {
        correct.reviewer_id: SimpleNamespace(total_votes=0, correct_votes=0),
        wrong.reviewer_id: SimpleNamespace(total_votes=0, correct_votes=0),
    }
    profile_repo.get_or_create.side_effect = lambda reviewer_id, **_: profiles[reviewer_id]

    await svc._update_expert_profiles([correct, wrong], final_overall=OverallVerdict.ALTERED)

    calls = {id(c.args[0]): c.kwargs for c in profile_repo.update.call_args_list}
    assert calls[id(profiles[correct.reviewer_id])]["correct_votes"] == 1
    assert calls[id(profiles[wrong.reviewer_id])]["correct_votes"] == 0
