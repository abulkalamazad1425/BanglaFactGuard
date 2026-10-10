"""Reviewer votes and justifications become public only after the final
decision, and never reveal reviewers' emails or ids."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.constants import OverallVerdict, SubmissionStatus
from app.features.expert_review.models import ExpertReview
from app.features.expert_review.public_votes import load_public_voting_details
from tests.helpers.db import add_completed_submission, add_multimodal_submission, add_user

WHY = "Matches the outlet's own report word for word."
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def review(sub, user, verdict, minute, *, admin=False):
    r = ExpertReview(submission_id=sub.id, reviewer_id=user.id, vote_overall_verdict=verdict, justification=WHY,
                     credibility_weight=1.0, status="finalized", is_admin_decision=admin)
    r.created_at = T0 + timedelta(minutes=minute)
    return r


async def test_an_admin_decision_is_published_with_every_vote_and_no_private_data(session):
    admin = await add_user(session, role="admin", full_name="Site Admin")
    named, unnamed = await add_user(session, role="expert", full_name="Expert One"), await add_user(session, role="expert")
    sub, result = await add_completed_submission(session, headline="h", submitter_id=None)
    session.add_all([review(sub, admin, OverallVerdict.ALTERED, 0, admin=True),
                     review(sub, named, OverallVerdict.FAKE, 1), review(sub, unnamed, OverallVerdict.REAL, 2)])
    await session.flush()
    assert await load_public_voting_details(session, sub) is None  # not final yet

    sub.status, result.overall_verdict = SubmissionStatus.FINALIZED, OverallVerdict.ALTERED
    await session.flush()
    details = await load_public_voting_details(session, sub)
    assert (details.final_verdict, details.decided_by) == (OverallVerdict.ALTERED, "ADMIN")
    assert [(v.reviewer_name, v.reviewer_role, v.overall_vote, v.is_final_decision) for v in details.votes] == [
        ("Expert One", "Expert", OverallVerdict.FAKE, False),
        ("Expert reviewer 2", "Expert", OverallVerdict.REAL, False),  # no name -> never the email
        ("Site Admin", "Admin", OverallVerdict.ALTERED, True),
    ]
    dumped = details.model_dump_json()
    assert all(u.email not in dumped and str(u.id) not in dumped for u in (admin, named, unnamed))


async def test_a_copy_shows_its_originals_expert_consensus_and_multimodal_claims_are_supported(session):
    expert = await add_user(session, role="expert")
    original, result = await add_completed_submission(session, headline="h", submitter_id=None,
                                                      overall_verdict=OverallVerdict.REAL)
    original.status = SubmissionStatus.FINALIZED
    copy, _ = await add_completed_submission(session, headline="h", submitter_id=None)
    copy.duplicate_of_submission_id = original.id
    session.add(review(original, expert, OverallVerdict.REAL, 0))
    await session.flush()
    details = await load_public_voting_details(session, copy)
    assert details.submission_id == copy.id and details.decided_by == "EXPERT_CONSENSUS" and len(details.votes) == 1

    mm, analysis = await add_multimodal_submission(session)
    mm.status = SubmissionStatus.FINALIZED
    await session.flush()
    assert await load_public_voting_details(session, mm) is None  # finalized status but no verdict stored
    analysis.expert_overall_verdict = OverallVerdict.FAKE
    await session.flush()
    assert (await load_public_voting_details(session, mm)).final_verdict == OverallVerdict.FAKE
