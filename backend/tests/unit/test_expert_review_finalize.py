"""
tests/unit/test_expert_review_finalize.py
==========================================
Unit tests for the credibility-weighted expert consensus engine:
_tally / _evaluate (pure functions), ExpertReviewService._finalize_or_escalate,
_resolve_weight, and the submit_vote guard clauses (conflict-of-interest,
duplicate vote, claim-not-open).

Covers the spec's own worked example and key test cases: weight activation
threshold N, T/M/margin finalization, ties escalating, Source=NOT_FOUND
making Content/Date N/A, the AI snapshot staying immutable after finalize,
and an expert being blocked from voting on their own submission or twice.
"""

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.constants import (
    ContentStatus,
    DateStatus,
    MultimodalPredictionLabel,
    OverallVerdict,
    SourceStatus,
    SubmissionStatus,
    SubmissionType,
)
from app.core.exceptions import DomainValidationError
from app.features.expert_review.models import ExpertReviewV2, VotingConfig
from app.features.expert_review.service import ExpertReviewService, _evaluate, _tally
from app.features.multimodal.models import MultimodalAnalysis
from app.features.submissions.models import Submission
from app.features.verification.models import VerificationResultV2


def _config(
    *,
    T: float = 5.0,
    M: int = 3,
    margin: float = 1.0,
    N: int = 10,
    max_review_votes: int | None = None,
    max_review_hours: int | None = None,
    max_tier_weight: float | None = None,
) -> VotingConfig:
    return VotingConfig(
        min_expert_votes=M,
        activation_threshold_votes=N,
        verified_threshold=T,
        lead_margin=margin,
        max_review_votes=max_review_votes,
        max_review_hours=max_review_hours,
        max_tier_weight=max_tier_weight,
    )


def _make_service():
    review_repo = AsyncMock()
    profile_repo = AsyncMock()
    tier_repo = AsyncMock()
    submission_repo = AsyncMock()
    result_repo = AsyncMock()
    multimodal_repo = AsyncMock()
    voting_config_repo = AsyncMock()
    audit_repo = AsyncMock()
    review_repo.session = MagicMock()
    svc = ExpertReviewService(
        review_repo=review_repo,
        profile_repo=profile_repo,
        tier_repo=tier_repo,
        submission_repo=submission_repo,
        result_repo=result_repo,
        multimodal_repo=multimodal_repo,
        voting_config_repo=voting_config_repo,
        audit_repo=audit_repo,
    )
    return {
        "svc": svc,
        "reviews": review_repo,
        "profiles": profile_repo,
        "tiers": tier_repo,
        "submissions": submission_repo,
        "results": result_repo,
        "multimodal": multimodal_repo,
        "voting_config": voting_config_repo,
        "audit": audit_repo,
    }


def _review(
    overall: OverallVerdict,
    weight: float,
    *,
    source: SourceStatus | None = None,
    content: ContentStatus | None = None,
    date_: DateStatus | None = None,
    reviewer_id: uuid.UUID | None = None,
) -> ExpertReviewV2:
    return ExpertReviewV2(
        id=uuid.uuid4(),
        submission_id=uuid.uuid4(),
        reviewer_id=reviewer_id or uuid.uuid4(),
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


def _result(source, content, date_, confidence=0.9) -> VerificationResultV2:
    return VerificationResultV2(
        id=uuid.uuid4(),
        submission_id=uuid.uuid4(),
        source_status=source,
        content_status=content,
        date_status=date_,
        confidence=confidence,
    )


def _submission(
    submission_type: SubmissionType,
    *,
    submitter_id: uuid.UUID | None = None,
    status: SubmissionStatus = SubmissionStatus.EXPERT_REVIEW,
    created_at: datetime | None = None,
) -> Submission:
    return Submission(
        id=uuid.uuid4(),
        submission_type=submission_type,
        content_hash="x",
        submitter_id=submitter_id,
        status=status,
        created_at=created_at or datetime.now(timezone.utc),
    )


def _multimodal_analysis(prediction, confidence_fake=0.8, confidence_real=0.2) -> MultimodalAnalysis:
    return MultimodalAnalysis(
        id=uuid.uuid4(),
        submission_id=uuid.uuid4(),
        image_object_key="k",
        prediction=prediction,
        confidence_fake=confidence_fake,
        confidence_real=confidence_real,
    )


# ─── _tally / _evaluate (pure functions) ───────────────────────────────


def test_tally_sums_weight_per_verdict_ignoring_ai():
    reviews = [
        _review(OverallVerdict.FAKE, 2.0),
        _review(OverallVerdict.FAKE, 1.5),
        _review(OverallVerdict.REAL, 1.0),
    ]
    weights = _tally(reviews, lambda r: r.vote_overall_verdict)
    assert weights == {OverallVerdict.FAKE: 3.5, OverallVerdict.REAL: 1.0}


def test_evaluate_fails_when_threshold_not_met():
    config = _config(T=5.0, M=3, margin=1.0)
    weights = {OverallVerdict.FAKE: 4.0, OverallVerdict.MISLEADING: 1.0}
    passes, leader = _evaluate(weights, voters=3, config=config, tie_break=None)
    assert passes is False
    assert leader == OverallVerdict.FAKE  # still reports the front-runner


def test_evaluate_fails_when_min_voters_not_met_even_if_threshold_met():
    """One very high-weight expert alone can't finalize — M stops that."""
    config = _config(T=5.0, M=3, margin=1.0)
    weights = {OverallVerdict.FAKE: 6.0}
    passes, _ = _evaluate(weights, voters=1, config=config, tie_break=None)
    assert passes is False


def test_evaluate_fails_when_margin_not_met():
    config = _config(T=5.0, M=2, margin=2.0)
    weights = {OverallVerdict.FAKE: 5.0, OverallVerdict.REAL: 4.0}  # margin only 1.0
    passes, _ = _evaluate(weights, voters=2, config=config, tie_break=None)
    assert passes is False


def test_evaluate_passes_when_all_three_conditions_met():
    config = _config(T=5.0, M=3, margin=1.0)
    weights = {OverallVerdict.FAKE: 5.5, OverallVerdict.MISLEADING: 1.0}
    passes, leader = _evaluate(weights, voters=4, config=config, tie_break=None)
    assert passes is True
    assert leader == OverallVerdict.FAKE


def test_evaluate_tie_does_not_pass_margin_and_prefers_tie_break_as_leader():
    config = _config(T=1.0, M=1, margin=0.5)
    weights = {OverallVerdict.FAKE: 2.0, OverallVerdict.REAL: 2.0}
    passes, leader = _evaluate(weights, voters=2, config=config, tie_break=OverallVerdict.REAL)
    assert passes is False  # margin is 0, fails the 0.5 requirement
    assert leader == OverallVerdict.REAL


# ─── Worked example from the spec (T=5, M=3, N=10) ─────────────────────


@pytest.mark.asyncio
async def test_worked_example_stays_open_then_finalizes_on_fourth_vote():
    ctx = _make_service()
    submission = _submission(SubmissionType.MULTIMODAL)
    config = _config(T=5.0, M=3, margin=1.0, N=10)
    ctx["voting_config"].get_or_create.return_value = config
    mm = _multimodal_analysis(MultimodalPredictionLabel.NON_FAKE)
    ctx["multimodal"].get_by_submission_id.return_value = mm

    # Two Gold (2.0) vote Fake, one new expert (1.0) votes Misleading: 4.0 < T=5.
    reviews = [
        _review(OverallVerdict.FAKE, 2.0),
        _review(OverallVerdict.FAKE, 2.0),
        _review(OverallVerdict.MISLEADING, 1.0),
    ]
    ctx["reviews"].get_for_submission.return_value = reviews

    await ctx["svc"]._finalize_or_escalate(submission)

    ctx["multimodal"].update.assert_not_awaited()
    ctx["submissions"].mark_finalized.assert_not_awaited()

    # A fourth vote, Silver (1.5), also Fake: 4.0 + 1.5 = 5.5 >= T, voters=4 >= M,
    # margin 5.5 - 1.0 = 4.5 >= 1.0 -> finalizes as Fake.
    reviews.append(_review(OverallVerdict.FAKE, 1.5))
    await ctx["svc"]._finalize_or_escalate(submission)

    ctx["multimodal"].update.assert_awaited_once()
    _, kwargs = ctx["multimodal"].update.call_args
    assert kwargs["expert_overall_verdict"] == OverallVerdict.FAKE
    ctx["submissions"].mark_finalized.assert_awaited_once()


# ─── _resolve_weight — activation threshold N ──────────────────────────


@pytest.mark.asyncio
async def test_resolve_weight_is_neutral_below_activation_threshold():
    ctx = _make_service()
    config = _config(N=10)
    profile = SimpleNamespace(total_votes=9, correct_votes=9)
    weight, tier = await ctx["svc"]._resolve_weight(profile, config)
    assert weight == 1.0
    assert tier is None
    ctx["tiers"].resolve_tier_for_accuracy.assert_not_awaited()


@pytest.mark.asyncio
async def test_resolve_weight_uses_tier_at_and_above_activation_threshold():
    ctx = _make_service()
    config = _config(N=10)
    profile = SimpleNamespace(total_votes=10, correct_votes=10)
    fake_tier = SimpleNamespace(id=uuid.uuid4(), weight=2.0)
    ctx["tiers"].resolve_tier_for_accuracy.return_value = fake_tier
    weight, tier = await ctx["svc"]._resolve_weight(profile, config)
    assert weight == 2.0
    assert tier is fake_tier


@pytest.mark.asyncio
async def test_resolve_weight_respects_max_tier_weight_cap():
    ctx = _make_service()
    config = _config(N=10, max_tier_weight=1.5)
    profile = SimpleNamespace(total_votes=50, correct_votes=50)
    fake_tier = SimpleNamespace(id=uuid.uuid4(), weight=3.0)
    ctx["tiers"].resolve_tier_for_accuracy.return_value = fake_tier
    weight, _ = await ctx["svc"]._resolve_weight(profile, config)
    assert weight == 1.5


# ─── Source=NOT_FOUND makes Content/Date N/A ───────────────────────────


@pytest.mark.asyncio
async def test_not_found_source_skips_content_and_date_entirely():
    ctx = _make_service()
    submission = _submission(SubmissionType.SOURCE_BASED)
    config = _config(T=2.0, M=2, margin=0.5)
    ctx["voting_config"].get_or_create.return_value = config
    result = _result(SourceStatus.CONFIRMED, ContentStatus.MATCHED, DateStatus.MATCHED, confidence=0.9)
    ctx["results"].get_by_submission_id.return_value = result

    reviews = [
        _review(OverallVerdict.FAKE, 1.5, source=SourceStatus.NOT_FOUND),
        _review(OverallVerdict.FAKE, 1.0, source=SourceStatus.NOT_FOUND),
    ]
    ctx["reviews"].get_for_submission.return_value = reviews

    await ctx["svc"]._finalize_or_escalate(submission)

    ctx["results"].update.assert_awaited_once()
    _, kwargs = ctx["results"].update.call_args
    assert kwargs["final_source_status"] == SourceStatus.NOT_FOUND
    assert kwargs["final_content_status"] is None
    assert kwargs["final_date_status"] is None
    assert kwargs["overall_verdict"] == OverallVerdict.FAKE


# ─── AI snapshot stays immutable; only final_* / overall_verdict move ──


@pytest.mark.asyncio
async def test_finalize_never_touches_the_ai_snapshot_fields():
    ctx = _make_service()
    submission = _submission(SubmissionType.SOURCE_BASED)
    config = _config(T=1.0, M=1, margin=0.0)
    ctx["voting_config"].get_or_create.return_value = config
    result = _result(SourceStatus.CONFIRMED, ContentStatus.MATCHED, DateStatus.MATCHED)
    ctx["results"].get_by_submission_id.return_value = result

    reviews = [
        _review(
            OverallVerdict.ALTERED,
            1.0,
            source=SourceStatus.CONFIRMED,
            content=ContentStatus.ALTERED,
            date_=DateStatus.MATCHED,
        )
    ]
    ctx["reviews"].get_for_submission.return_value = reviews

    await ctx["svc"]._finalize_or_escalate(submission)

    _, kwargs = ctx["results"].update.call_args
    # Only final_* and overall_verdict/finalized_at are in the update call —
    # source_status/content_status/date_status (the AI's own columns) are
    # never passed to update() at all.
    assert "source_status" not in kwargs
    assert "content_status" not in kwargs
    assert "date_status" not in kwargs
    assert kwargs["final_content_status"] == ContentStatus.ALTERED


# ─── Ties / deadlock -> escalation after the configured window ────────


@pytest.mark.asyncio
async def test_tie_stays_open_until_max_review_votes_then_escalates():
    ctx = _make_service()
    submission = _submission(SubmissionType.MULTIMODAL)
    config = _config(T=1.0, M=1, margin=0.5, max_review_votes=2)
    ctx["voting_config"].get_or_create.return_value = config
    mm = _multimodal_analysis(MultimodalPredictionLabel.NON_FAKE)
    ctx["multimodal"].get_by_submission_id.return_value = mm

    # Perfectly tied -> margin never satisfied -> never finalizes.
    reviews = [
        _review(OverallVerdict.FAKE, 1.0),
        _review(OverallVerdict.REAL, 1.0),
    ]
    ctx["reviews"].get_for_submission.return_value = reviews

    await ctx["svc"]._finalize_or_escalate(submission)

    ctx["multimodal"].update.assert_not_awaited()
    ctx["submissions"].set_status.assert_awaited_once()
    args, _ = ctx["submissions"].set_status.call_args
    assert args[1] == SubmissionStatus.ESCALATED


@pytest.mark.asyncio
async def test_no_escalation_before_window_exhausted():
    ctx = _make_service()
    submission = _submission(SubmissionType.MULTIMODAL)
    config = _config(T=1.0, M=1, margin=0.5, max_review_votes=5)
    ctx["voting_config"].get_or_create.return_value = config
    mm = _multimodal_analysis(MultimodalPredictionLabel.NON_FAKE)
    ctx["multimodal"].get_by_submission_id.return_value = mm

    reviews = [_review(OverallVerdict.FAKE, 1.0), _review(OverallVerdict.REAL, 1.0)]
    ctx["reviews"].get_for_submission.return_value = reviews

    await ctx["svc"]._finalize_or_escalate(submission)

    ctx["submissions"].set_status.assert_not_awaited()


@pytest.mark.asyncio
async def test_escalates_after_max_review_hours_even_with_few_votes():
    ctx = _make_service()
    old_time = datetime.now(timezone.utc) - timedelta(hours=100)
    submission = _submission(SubmissionType.MULTIMODAL, created_at=old_time)
    config = _config(T=1.0, M=1, margin=0.5, max_review_hours=48)
    ctx["voting_config"].get_or_create.return_value = config
    mm = _multimodal_analysis(MultimodalPredictionLabel.NON_FAKE)
    ctx["multimodal"].get_by_submission_id.return_value = mm

    reviews = [_review(OverallVerdict.FAKE, 1.0), _review(OverallVerdict.REAL, 1.0)]
    ctx["reviews"].get_for_submission.return_value = reviews

    await ctx["svc"]._finalize_or_escalate(submission)

    ctx["submissions"].set_status.assert_awaited_once()


# ─── submit_vote guard clauses ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_submit_vote_rejects_the_submitter_voting_on_their_own_claim():
    ctx = _make_service()
    expert_id = uuid.uuid4()
    submission = _submission(SubmissionType.MULTIMODAL, submitter_id=expert_id)
    ctx["submissions"].get_by_id_locked.return_value = submission

    with pytest.raises(DomainValidationError):
        await ctx["svc"].submit_vote(
            submission_id=submission.id,
            expert_id=expert_id,
            overall_verdict=OverallVerdict.REAL,
            source_status=None,
            content_status=None,
            date_status=None,
            justification="x" * 60,
        )


@pytest.mark.asyncio
async def test_submit_vote_rejects_a_second_vote_from_the_same_expert():
    ctx = _make_service()
    expert_id = uuid.uuid4()
    submission = _submission(SubmissionType.MULTIMODAL)
    ctx["submissions"].get_by_id_locked.return_value = submission
    ctx["reviews"].get_by_submission_and_reviewer.return_value = _review(OverallVerdict.REAL, 1.0)

    with pytest.raises(DomainValidationError):
        await ctx["svc"].submit_vote(
            submission_id=submission.id,
            expert_id=expert_id,
            overall_verdict=OverallVerdict.REAL,
            source_status=None,
            content_status=None,
            date_status=None,
            justification="x" * 60,
        )


@pytest.mark.asyncio
async def test_submit_vote_rejects_voting_on_a_claim_not_open_for_review():
    ctx = _make_service()
    submission = _submission(SubmissionType.MULTIMODAL, status=SubmissionStatus.FINALIZED)
    ctx["submissions"].get_by_id_locked.return_value = submission

    with pytest.raises(DomainValidationError):
        await ctx["svc"].submit_vote(
            submission_id=submission.id,
            expert_id=uuid.uuid4(),
            overall_verdict=OverallVerdict.REAL,
            source_status=None,
            content_status=None,
            date_status=None,
            justification="x" * 60,
        )


@pytest.mark.asyncio
async def test_submit_vote_locks_the_submission_row():
    """The row lock is what makes concurrent-vote finalization safe — assert
    the locking accessor is actually what's used, not a plain unlocked read."""
    ctx = _make_service()
    submission = _submission(SubmissionType.MULTIMODAL)
    ctx["submissions"].get_by_id_locked.return_value = submission
    ctx["reviews"].get_by_submission_and_reviewer.return_value = None
    def _echo(r):
        r.created_at = r.created_at or datetime.now(timezone.utc)
        r.updated_at = r.updated_at or datetime.now(timezone.utc)
        return r

    ctx["reviews"].create.side_effect = _echo
    mm = _multimodal_analysis(MultimodalPredictionLabel.NON_FAKE)
    ctx["multimodal"].get_by_submission_id.return_value = mm
    ctx["voting_config"].get_or_create.return_value = _config()
    ctx["profiles"].get_or_create.return_value = SimpleNamespace(total_votes=0, correct_votes=0)
    ctx["reviews"].get_for_submission.return_value = []

    await ctx["svc"].submit_vote(
        submission_id=submission.id,
        expert_id=uuid.uuid4(),
        overall_verdict=OverallVerdict.REAL,
        source_status=None,
        content_status=None,
        date_status=None,
        justification="x" * 60,
    )

    ctx["submissions"].get_by_id_locked.assert_awaited_once()
    ctx["submissions"].get_by_id.assert_not_called()


# ─── _update_expert_profiles (correctness scoring) ─────────────────────


@pytest.mark.asyncio
async def test_update_expert_profiles_scores_on_overall_match():
    ctx = _make_service()
    correct = _review(OverallVerdict.ALTERED, 1.0)
    wrong = _review(OverallVerdict.REAL, 1.0)

    profiles = {
        correct.reviewer_id: SimpleNamespace(total_votes=0, correct_votes=0),
        wrong.reviewer_id: SimpleNamespace(total_votes=0, correct_votes=0),
    }
    ctx["profiles"].get_or_create.side_effect = lambda reviewer_id, **_: profiles[reviewer_id]

    await ctx["svc"]._update_expert_profiles([correct, wrong], final_overall=OverallVerdict.ALTERED)

    calls = {id(c.args[0]): c.kwargs for c in ctx["profiles"].update.call_args_list}
    assert calls[id(profiles[correct.reviewer_id])]["correct_votes"] == 1
    assert calls[id(profiles[wrong.reviewer_id])]["correct_votes"] == 0
