"""Expert statistics are derived from finalized claims (so they cannot drift),
the score exists only after N such votes, and tiers cover accuracy inclusively."""

from __future__ import annotations

import uuid

from sqlalchemy import update

from app.core.constants import OverallVerdict, SubmissionStatus
from app.features.expert_review.models import CredibilityWeightTier, ExpertReview
from app.features.expert_review.repository import (
    CredibilityWeightTierRepository,
    ExpertProfileRepository,
    VotingConfigRepository,
)
from app.features.verification.models import VerificationResult
from tests.helpers.db import add_completed_submission, add_user


async def claim(session, n, status, final=None):
    sub, _ = await add_completed_submission(session, headline=f"দাবি {n}", submitter_id=None, overall_verdict=final)
    sub.status = status
    await session.flush()
    return sub


def vote(sub, reviewer, verdict, *, admin=False):
    return ExpertReview(id=uuid.uuid4(), submission_id=sub.id, reviewer_id=reviewer.id, vote_overall_verdict=verdict,
                        credibility_weight=1.0, status="pending", is_admin_decision=admin)


async def test_only_votes_on_finalized_claims_count_and_correct_means_the_final_verdict(session):
    expert, admin = await add_user(session, role="expert"), await add_user(session, role="admin")
    real = [await claim(session, i, SubmissionStatus.FINALIZED, OverallVerdict.REAL) for i in range(3)]
    fake = await claim(session, 9, SubmissionStatus.FINALIZED, OverallVerdict.FAKE)
    open_ = await claim(session, 10, SubmissionStatus.EXPERT_REVIEW)
    escalated = await claim(session, 11, SubmissionStatus.ESCALATED)
    session.add_all([vote(s, expert, OverallVerdict.REAL) for s in real] + [
        vote(fake, expert, OverallVerdict.REAL), vote(open_, expert, OverallVerdict.REAL),
        vote(escalated, expert, OverallVerdict.FAKE), vote(fake, admin, OverallVerdict.FAKE, admin=True),
    ])
    await session.flush()
    repo = ExpertProfileRepository(session)
    assert await repo.finalized_vote_counts(expert.id) == (4, 3)
    assert await repo.finalized_vote_counts(admin.id) == (0, 0)

    profile = await repo.get_or_create(expert.id, initial_score=0.5)  # a legacy seed score is ignored
    assert profile.credibility_score is None and await repo.get_or_create(expert.id) is profile
    profile = await repo.refresh_stats(profile, activation_threshold=5)
    assert (profile.total_votes, profile.correct_votes, profile.credibility_score) == (4, 3, None)  # below N

    escalated.status = SubmissionStatus.FINALIZED  # an administrator decided it: the vote now counts
    await session.execute(update(VerificationResult).where(VerificationResult.submission_id == escalated.id)
                          .values(overall_verdict=OverallVerdict.REAL))
    await session.flush()
    profile = await repo.refresh_stats(profile, activation_threshold=5)
    assert (profile.total_votes, profile.correct_votes, profile.credibility_score) == (5, 3, 0.6)

    await session.execute(ExpertReview.__table__.delete().where(ExpertReview.submission_id == real[0].id))
    profile = await repo.refresh_stats(profile, activation_threshold=5)
    assert (profile.total_votes, profile.correct_votes, profile.credibility_score) == (4, 2, None)  # never drifts


async def test_tiers_resolve_inclusively_among_active_ones_and_config_exists_once(session):
    session.add_all([
        CredibilityWeightTier(label="Bronze", min_accuracy_pct=0.0, max_accuracy_pct=60.0, weight=1.0, is_active=True),
        CredibilityWeightTier(label="Gold", min_accuracy_pct=60.0, max_accuracy_pct=100.0, weight=2.0, is_active=True),
        CredibilityWeightTier(label="Old", min_accuracy_pct=0.0, max_accuracy_pct=100.0, weight=9.0, is_active=False),
    ])
    await session.flush()
    tiers = CredibilityWeightTierRepository(session)
    assert [t.label for t in await tiers.get_active_tiers()] == ["Bronze", "Gold"]
    assert (await tiers.resolve_tier_for_accuracy(60.0)).label == "Bronze"  # inclusive: lowest matching tier
    assert (await tiers.resolve_tier_for_accuracy(100.0)).label == "Gold"
    assert await tiers.resolve_tier_for_accuracy(101.0) is None

    configs = VotingConfigRepository(session)
    first = await configs.get_or_create()
    assert first.min_expert_votes == 3 and await configs.get_or_create() is first
