"""Activation threshold N and accuracy count only votes on claims whose final
decision is complete; the counters are derived from the data, so they cannot
drift when a claim is removed."""

from __future__ import annotations

import uuid

from sqlalchemy import update

from app.core.constants import OverallVerdict, SubmissionStatus
from app.features.expert_review.models import ExpertProfile, ExpertReview
from app.features.expert_review.repository import ExpertProfileRepository
from app.features.verification.models import VerificationResult
from app.shared.models_registry import Base
from tests.unit.db_helpers import add_completed_submission, add_user, make_session_factory


async def _db():
    engine, factory = await make_session_factory()
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=[ExpertProfile.__table__]))
        # The real table has Postgres ARRAY columns; the stats query only needs these.
        await conn.exec_driver_sql(
            "CREATE TABLE multimodal_analysis (id CHAR(32) PRIMARY KEY, submission_id CHAR(32), "
            "expert_overall_verdict VARCHAR(20))"
        )
    return engine, factory


async def _claim(session, n, status, final=None):
    sub, _ = await add_completed_submission(
        session, headline=f"দাবি {n}", submitter_id=None, overall_verdict=final
    )
    sub.status = status
    await session.flush()
    return sub


def _vote(sub, reviewer_id, verdict, *, admin=False):
    return ExpertReview(
        id=uuid.uuid4(), submission_id=sub.id, reviewer_id=reviewer_id,
        vote_overall_verdict=verdict, credibility_weight=1.0,
        status="finalized" if sub.status == SubmissionStatus.FINALIZED else "pending",
        is_admin_decision=admin,
    )


async def test_only_votes_on_finalized_claims_count_and_correct_means_matches_the_final_verdict():
    engine, factory = await _db()
    async with factory() as session:
        expert = await add_user(session, role="expert")
        admin = await add_user(session, role="admin")
        fin_real = [await _claim(session, i, SubmissionStatus.FINALIZED, OverallVerdict.REAL) for i in range(3)]
        fin_fake = await _claim(session, 9, SubmissionStatus.FINALIZED, OverallVerdict.FAKE)
        open_claim = await _claim(session, 10, SubmissionStatus.EXPERT_REVIEW)
        escalated = await _claim(session, 11, SubmissionStatus.ESCALATED)
        session.add_all(
            [_vote(s, expert.id, OverallVerdict.REAL) for s in fin_real]      # 3 correct
            + [_vote(fin_fake, expert.id, OverallVerdict.REAL)]               # 1 wrong
            + [_vote(open_claim, expert.id, OverallVerdict.REAL),            # not final yet
               _vote(escalated, expert.id, OverallVerdict.FAKE),             # not final yet
               _vote(fin_fake, admin.id, OverallVerdict.FAKE, admin=True)]   # admin row
        )
        await session.flush()
        repo = ExpertProfileRepository(session)

        assert await repo.finalized_vote_counts(expert.id) == (4, 3)
        assert await repo.finalized_vote_counts(admin.id) == (0, 0)

        profile = await repo.get_or_create(expert.id)
        profile = await repo.refresh_stats(profile, activation_threshold=5)
        assert (profile.total_votes, profile.correct_votes, profile.credibility_score) == (4, 3, None)

        # The escalated claim gets an administrator's final decision: the
        # expert's vote on it now counts (wrong: FAKE vs final REAL).
        escalated.status = SubmissionStatus.FINALIZED
        await session.execute(update(VerificationResult)
                              .where(VerificationResult.submission_id == escalated.id)
                              .values(overall_verdict=OverallVerdict.REAL))
        await session.flush()
        profile = await repo.refresh_stats(profile, activation_threshold=5)
        assert (profile.total_votes, profile.correct_votes) == (5, 3)
        assert profile.credibility_score == 0.6  # N reached: 3 correct of 5 finalized

        # A removed claim no longer counts (an incremented counter kept it).
        await session.execute(ExpertReview.__table__.delete().where(ExpertReview.submission_id == fin_real[0].id))
        await session.flush()
        profile = await repo.refresh_stats(profile, activation_threshold=5)
        assert (profile.total_votes, profile.correct_votes, profile.credibility_score) == (4, 2, None)
    await engine.dispose()
