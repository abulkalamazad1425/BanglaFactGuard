"""Overall-vote-only decisions, escalation to admin, admin final decisions and
public voting details — against a real (SQLite) database, so permission,
status-transition and duplicate-notification rules are exercised end to end
through the service layer."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import ARRAY, func, select
from sqlalchemy.ext.compiler import compiles

from app.core.constants import (
    ContentStatus,
    DateStatus,
    HeadlineAlterationStatus,
    OverallVerdict,
    SourceStatus,
    SubmissionStatus,
)
from app.core.exceptions import DomainValidationError, PermissionDeniedError
from app.features.expert_review.escalation import (
    ESCALATION_NOTIFICATION_TYPE,
    _service,
    escalation_message,
    sweep_review_limits,
)
from app.features.expert_review.models import ExpertProfile, VotingConfig
from app.features.expert_review.public_votes import load_public_voting_details
from app.features.multimodal.models import MultimodalAnalysis
from app.features.notifications.models import Notification
from app.features.submissions.repository import SubmissionRepository
from app.features.verification.headline_status import derive_headline_status
from app.shared.utils.headline_preview import headline_preview
from tests.unit.db_helpers import add_completed_submission, add_user, make_session_factory


@compiles(ARRAY, "sqlite")
def _array_sqlite(type_, compiler, **kw):  # pragma: no cover - trivial shim
    return "JSON"


JUSTIFICATION = "The claimed outlet's own report contradicts the circulated headline in detail."
HEADLINE = "ঢাকায় আজ ভারী বৃষ্টিতে জলাবদ্ধতা, অফিসগামীদের চরম দুর্ভোগ"


@pytest.fixture
async def db():
    engine, factory = await make_session_factory()
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda c: [
                t.__table__.create(c)
                for t in (VotingConfig, ExpertProfile, MultimodalAnalysis)
            ]
        )
    yield factory
    await engine.dispose()


async def _setup(session, *, max_votes=None, max_hours=None, T=2.0, M=2, margin=1.0, age_hours=0):
    session.add(VotingConfig(
        min_expert_votes=M, activation_threshold_votes=10, verified_threshold=T,
        lead_margin=margin, max_review_votes=max_votes, max_review_hours=max_hours,
    ))
    admin = await add_user(session, role="admin")
    experts = [await add_user(session, role="expert") for _ in range(3)]
    sub, _ = await add_completed_submission(session, headline=HEADLINE, submitter_id=None)
    sub.created_at = datetime.now(timezone.utc) - timedelta(hours=age_hours)
    await session.flush()
    return admin, experts, sub


async def _vote(session, voter, sub, verdict, role="expert", **supplementary):
    return await _service(session).submit_vote(
        sub.id, voter.id, verdict,
        supplementary.get("source"), supplementary.get("content"), supplementary.get("date"),
        JUSTIFICATION, voter_role=role,
    )


async def _escalation_notes(session) -> int:
    return (await session.execute(
        select(func.count()).select_from(Notification).where(Notification.notification_type == ESCALATION_NOTIFICATION_TYPE)
    )).scalar_one()


# ─── escalation ─────────────────────────────────────────────────────────


async def test_time_limit_escalates_without_any_vote_and_notifies_admin_once(db):
    async with db() as s:
        admin, _, sub = await _setup(s, max_hours=24, age_hours=25)
        assert await sweep_review_limits(s) == 1
        await s.commit()
        assert (await SubmissionRepository(s).get_by_id(sub.id)).status == SubmissionStatus.ESCALATED
        assert sub.escalated_at is not None
        assert await sweep_review_limits(s) == 0  # already escalated: no second transition
        note = (await s.execute(select(Notification))).scalar_one()
        assert note.user_id == admin.id
        assert note.link_url == f"/admin/review-queue/{sub.id}"
        assert note.body == "Expert reviewers are having difficulty deciding this claim: ঢাকায় আজ ভারী বৃষ্টিতে জলাবদ্ধতা,..."


async def test_unconfigured_limits_never_escalate(db):
    async with db() as s:
        _, experts, sub = await _setup(s, age_hours=10_000)
        await _vote(s, experts[0], sub, OverallVerdict.FAKE)
        await _vote(s, experts[1], sub, OverallVerdict.REAL)
        assert await sweep_review_limits(s) == 0
        assert sub.status == SubmissionStatus.EXPERT_REVIEW


async def test_time_limit_not_yet_reached_keeps_claim_open(db):
    async with db() as s:
        _, _, sub = await _setup(s, max_hours=24, age_hours=23)
        assert await sweep_review_limits(s) == 0
        assert sub.status == SubmissionStatus.EXPERT_REVIEW


async def test_vote_limit_escalates_on_the_deciding_vote_when_overall_is_split(db):
    async with db() as s:
        _, experts, sub = await _setup(s, max_votes=2, T=2.0, M=2)
        # Unanimous supplementary findings do not help a split overall vote.
        same = dict(source=SourceStatus.CONFIRMED, content=ContentStatus.MATCHED, date=DateStatus.MATCHED)
        await _vote(s, experts[0], sub, OverallVerdict.FAKE, **same)
        assert sub.status == SubmissionStatus.EXPERT_REVIEW
        await _vote(s, experts[1], sub, OverallVerdict.REAL, **same)
        assert sub.status == SubmissionStatus.ESCALATED
        assert await _escalation_notes(s) == 1


async def test_agreeing_overall_votes_finalize_despite_conflicting_supplementary_findings(db):
    async with db() as s:
        _, experts, sub = await _setup(s, max_votes=2, T=2.0, M=2)
        await _vote(s, experts[0], sub, OverallVerdict.FAKE, source=SourceStatus.NOT_FOUND)
        await _vote(s, experts[1], sub, OverallVerdict.FAKE, source=SourceStatus.CONFIRMED,
                    content=ContentStatus.ALTERED, date=DateStatus.MISMATCHED)
        assert sub.status == SubmissionStatus.FINALIZED
        assert await _escalation_notes(s) == 0


# ─── permissions on escalated claims ────────────────────────────────────


async def test_only_admin_can_view_and_decide_an_escalated_claim(db):
    async with db() as s:
        admin, experts, sub = await _setup(s, max_votes=2)
        await _vote(s, experts[0], sub, OverallVerdict.FAKE)
        await _vote(s, experts[1], sub, OverallVerdict.REAL)
        assert sub.status == SubmissionStatus.ESCALATED
        svc = _service(s)

        with pytest.raises(PermissionDeniedError):
            await _vote(s, experts[2], sub, OverallVerdict.FAKE)
        with pytest.raises(PermissionDeniedError):
            await svc.get_queue_item(sub.id, viewer_id=experts[2].id, viewer_role="expert")
        assert await svc.get_queue(experts[2].id, viewer_role="expert") == []

        item = await svc.get_queue_item(sub.id, viewer_id=admin.id, viewer_role="admin")
        assert item.can_vote is True and item.decision_mode == "ADMIN_FINAL"
        admin_queue = await svc.get_queue(admin.id, viewer_role="admin", state="escalated")
        assert [q.submission_id for q in admin_queue] == [str(sub.id)]


async def test_admin_is_view_only_on_claims_that_are_not_escalated(db):
    async with db() as s:
        admin, _, sub = await _setup(s)
        svc = _service(s)
        item = await svc.get_queue_item(sub.id, viewer_id=admin.id, viewer_role="admin")
        assert item.can_vote is False
        with pytest.raises(PermissionDeniedError):
            await _vote(s, admin, sub, OverallVerdict.REAL, role="admin")
        assert sub.status == SubmissionStatus.EXPERT_REVIEW


async def test_admin_decision_is_final_and_overrides_the_expert_majority(db):
    async with db() as s:
        admin, experts, sub = await _setup(s, max_votes=3, T=10.0, M=3)
        await _vote(s, experts[0], sub, OverallVerdict.FAKE)
        await _vote(s, experts[1], sub, OverallVerdict.FAKE)
        await _vote(s, experts[2], sub, OverallVerdict.REAL)
        assert sub.status == SubmissionStatus.ESCALATED  # T=10 unreachable

        repo = SubmissionRepository(s)
        _, total = await repo.search(review_state="review")
        assert total == 1  # escalated claim stays Under Review in Fact Explorer
        assert await load_public_voting_details(s, sub) is None  # nothing public yet

        await _vote(s, admin, sub, OverallVerdict.MISLEADING, role="admin")
        assert sub.status == SubmissionStatus.FINALIZED
        from app.features.verification.repository import ResultRepository
        result = await ResultRepository(s).get_by_submission_id(sub.id)
        assert result.overall_verdict == OverallVerdict.MISLEADING
        _, total = await repo.search(review_state="finalized")
        assert total == 1

        # Experts' accuracy is scored against the admin's decision.
        profile = (await s.execute(select(ExpertProfile).where(ExpertProfile.user_id == experts[0].id))).scalar_one()
        assert (profile.total_votes, profile.correct_votes) == (1, 0)

        with pytest.raises(PermissionDeniedError):  # a second admin decision is refused
            await _vote(s, admin, sub, OverallVerdict.REAL, role="admin")
        with pytest.raises(DomainValidationError):  # experts cannot reopen it
            await _service(s).edit_vote(
                (await s.execute(select(ExpertReview_id(experts[0].id, sub.id)))).scalar_one(),
                experts[0].id, OverallVerdict.REAL, None, None, None, None,
            )


def ExpertReview_id(reviewer_id, submission_id):
    from app.features.expert_review.models import ExpertReview

    return select(ExpertReview.id).where(
        ExpertReview.reviewer_id == reviewer_id, ExpertReview.submission_id == submission_id
    ).scalar_subquery()


# ─── public voting details ──────────────────────────────────────────────


async def test_public_voting_details_after_final_decision_mark_the_admin(db):
    async with db() as s:
        admin, experts, sub = await _setup(s, max_votes=2)
        admin.full_name = "Site Admin"
        experts[0].full_name = "Expert One"
        await _vote(s, experts[0], sub, OverallVerdict.FAKE)
        await _vote(s, experts[1], sub, OverallVerdict.REAL)
        assert await load_public_voting_details(s, sub) is None
        await _vote(s, admin, sub, OverallVerdict.ALTERED, role="admin")

        details = await load_public_voting_details(s, sub)
        assert details.final_verdict == OverallVerdict.ALTERED and details.decided_by == "ADMIN"
        assert [(v.reviewer_role, v.overall_vote, v.is_final_decision) for v in details.votes] == [
            ("Expert", OverallVerdict.FAKE, False),
            ("Expert", OverallVerdict.REAL, False),
            ("Admin", OverallVerdict.ALTERED, True),
        ]
        assert details.votes[0].reviewer_name == "Expert One"
        assert details.votes[1].reviewer_name == "Expert reviewer 2"  # no name -> no email fallback
        assert all(v.justification == JUSTIFICATION for v in details.votes)
        dumped = details.model_dump_json()
        for user in (admin, *experts):
            assert user.email not in dumped and str(user.id) not in dumped


async def test_public_voting_details_for_expert_consensus(db):
    async with db() as s:
        _, experts, sub = await _setup(s, T=2.0, M=2)
        await _vote(s, experts[0], sub, OverallVerdict.REAL)
        assert await load_public_voting_details(s, sub) is None
        await _vote(s, experts[1], sub, OverallVerdict.REAL)
        details = await load_public_voting_details(s, sub)
        assert details.decided_by == "EXPERT_CONSENSUS" and len(details.votes) == 2
        assert not any(v.is_final_decision for v in details.votes)


# ─── display mappings ───────────────────────────────────────────────────


@pytest.mark.parametrize("headline,expected", [
    ("One two three four five six", "One two three four five..."),
    ("One two three four five", "One two three four five"),
    ("  ঢাকায়   আজ ভারী\tবৃষ্টি  ", "ঢাকায় আজ ভারী বৃষ্টি"),
    ("এক দুই তিন চার পাঁচ ছয়", "এক দুই তিন চার পাঁচ..."),
    ("   ", ""),
    (None, ""),
])
def test_headline_preview(headline, expected):
    assert headline_preview(headline) == expected


def test_escalation_message_uses_the_preview():
    assert escalation_message("Short claim") == "Expert reviewers are having difficulty deciding this claim: Short claim"


@pytest.mark.parametrize("kwargs,expected", [
    (dict(content_status=ContentStatus.ALTERED, exact_match=True), HeadlineAlterationStatus.ALTERED),
    (dict(content_status=ContentStatus.MATCHED, exact_match=True), HeadlineAlterationStatus.EXACT_MATCHED),
    (dict(content_status=ContentStatus.MATCHED, exact_match=False, claim_headline="ক খ", source_title="ক খ"),
     HeadlineAlterationStatus.MEANING_PRESERVED),  # stored flag wins over a re-check
    (dict(content_status=ContentStatus.MATCHED, basis="semantic_equivalence"), HeadlineAlterationStatus.MEANING_PRESERVED),
    # Legacy row without the flag: exactness re-checked with the exact-match normalisation only.
    (dict(content_status=ContentStatus.MATCHED, claim_headline="ঢাকায়  বৃষ্টি।", source_title="ঢাকায় বৃষ্টি"),
     HeadlineAlterationStatus.EXACT_MATCHED),
    (dict(content_status=ContentStatus.MATCHED, claim_headline="ঢাকায় বৃষ্টি", source_title="ঢাকায়, বৃষ্টি"),
     HeadlineAlterationStatus.MEANING_PRESERVED),
    (dict(content_status=ContentStatus.MATCHED), HeadlineAlterationStatus.MEANING_PRESERVED),  # no evidence
    (dict(content_status=None), None),
])
def test_headline_status_mapping(kwargs, expected):
    status = kwargs.pop("content_status")
    assert derive_headline_status(status, **kwargs) == expected


async def test_preliminary_notification_uses_headline_preview(db):
    from app.features.notifications.service import notify_once

    async with db() as s:
        user = await add_user(s)
        await notify_once(
            s, user_id=user.id, notification_type="VERIFICATION_COMPLETE", link_url="/verify/x",
            title="ignored", body="ignored", headline="এক দুই তিন চার পাঁচ ছয় সাত",
        )
        note = (await s.execute(select(Notification))).scalar_one()
        assert (note.title, note.body) == ("Preliminary result ready", "এক দুই তিন চার পাঁচ...")
        assert "automatic check" not in note.body
