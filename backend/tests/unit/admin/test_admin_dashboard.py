"""The admin home page: what needs action now, recent changes and expert activity."""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.constants import OverallVerdict, SubmissionStatus
from app.features.admin.dashboard import build_admin_dashboard
from app.features.expert_review.models import ExpertProfile, ExpertReview
from tests.helpers.db import add_completed_submission, add_multimodal_submission, add_user


async def test_dashboard_lists_and_counts(session):
    now = datetime.now(timezone.utc)
    admin = await add_user(session, role="admin", full_name="Admin")
    active = await add_user(session, role="expert", full_name="Active Expert")
    await add_user(session, role="expert", full_name="Idle", is_active=False)
    session.add(ExpertProfile(user_id=active.id, area_of_expertise="General", total_votes=2, correct_votes=2,
                              completed_reviews_count=2))

    escalated, _ = await add_completed_submission(session, headline="জটিল দাবি", submitter_id=None)
    escalated.status, escalated.escalated_at = SubmissionStatus.ESCALATED, now
    pending, _ = await add_completed_submission(session, headline="চলমান", submitter_id=None)
    decided, decided_result = await add_completed_submission(session, headline="সিদ্ধান্ত", submitter_id=None,
                                                             overall_verdict=OverallVerdict.FAKE, finalized_at=now)
    decided.status = SubmissionStatus.FINALIZED
    mm, analysis = await add_multimodal_submission(session, expert_overall_verdict=OverallVerdict.REAL, finalized_at=now)
    mm.status = SubmissionStatus.FINALIZED
    failed, _ = await add_completed_submission(session, headline="ব্যর্থ", submitter_id=None)
    failed.status = SubmissionStatus.FAILED
    copy, _ = await add_completed_submission(session, headline="চলমান", submitter_id=None)
    copy.duplicate_of_submission_id = pending.id
    session.add_all([
        ExpertReview(submission_id=decided.id, reviewer_id=active.id, vote_overall_verdict=OverallVerdict.FAKE,
                     credibility_weight=1.0, status="finalized"),
        ExpertReview(submission_id=escalated.id, reviewer_id=admin.id, vote_overall_verdict=OverallVerdict.REAL,
                     credibility_weight=1.0, status="finalized", is_admin_decision=True),
    ])
    await session.flush()

    d = await build_admin_dashboard(session)
    assert (d.escalated_count, d.pending_review_count, d.processing_count) == (1, 1, 0)
    assert (d.failed_last_7_days, d.finalized_last_7_days, d.total_submissions, d.submissions_last_7_days) == (1, 2, 6, 6)
    assert (d.active_experts, d.inactive_experts) == (1, 1)
    assert [c.headline for c in d.escalated_claims] == ["জটিল দাবি"] and d.escalated_claims[0].decided_by_admin
    assert [c.submission_id for c in d.oldest_pending_reviews] == [str(pending.id)]
    decisions = {c.submission_id: c for c in d.recent_decisions}
    assert decisions[str(decided.id)].final_verdict == "FAKE" and decisions[str(decided.id)].vote_count == 1
    assert decisions[str(mm.id)].final_verdict == "REAL"
    assert str(copy.id) not in {c.submission_id for c in d.recent_submissions}
    assert d.experts[0].full_name == "Active Expert" and d.experts[0].total_votes == 2 and d.experts[0].last_vote_at
    assert {(a.kind, a.actor) for a in d.recent_activity} == {("VOTE", "Active Expert"), ("ADMIN_DECISION", "Admin")}
