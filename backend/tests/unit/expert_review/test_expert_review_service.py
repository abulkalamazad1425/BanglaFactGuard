"""Credibility-weighted expert review. Only the OVERALL votes decide; a claim
finalizes when the leader clears threshold T, M voters and the lead margin,
escalates to an administrator when a configured review limit is exceeded,
and an administrator's decision on an escalated claim is final."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import func, select

from app.core.constants import (
    ContentStatus,
    DateStatus,
    HeadlineAlterationStatus,
    MultimodalPredictionLabel,
    OverallVerdict,
    SourceStatus,
    SubmissionStatus,
    SubmissionType,
)
from app.core.exceptions import DomainValidationError, PermissionDeniedError
from app.features.expert_review.escalation import ESCALATION_NOTIFICATION_TYPE, _service
from app.features.expert_review.models import (
    CredibilityWeightTier,
    ExpertProfile,
    ExpertReview,
    VotingConfig,
)
from app.features.expert_review.service import _evaluate, _tally, review_limits_exceeded
from app.features.notifications.models import Notification
from app.features.submissions.models import PhotocardExtraction, RetrievedArticle, Submission
from app.features.verification.repository import ResultRepository
from tests.helpers.db import (
    add_completed_submission,
    add_multimodal_submission,
    add_user,
    add_voting_config,
)

WHY = "The claimed outlet's own report contradicts the circulated headline in detail."
F, R, M, A = OverallVerdict.FAKE, OverallVerdict.REAL, OverallVerdict.MISLEADING, OverallVerdict.ALTERED


def config(T=5.0, M=3, margin=1.0, N=10, votes=None, hours=None) -> VotingConfig:
    return VotingConfig(verified_threshold=T, min_expert_votes=M, lead_margin=margin, activation_threshold_votes=N,
                        max_review_votes=votes, max_review_hours=hours)


# ── the decision rules (pure) ────────────────────────────────────────────

@pytest.mark.parametrize("weights,voters,cfg,passes,leader", [
    ({F: 4.0, M: 1.0}, 3, config(), False, F),            # below threshold T: still reports the front-runner
    ({F: 6.0}, 1, config(), False, F),                    # one heavy expert alone: M stops it
    ({F: 5.0, R: 4.0}, 2, config(M=2, margin=2.0), False, F),  # lead margin not met
    ({F: 5.5, M: 1.0}, 4, config(), True, F),
    ({F: 2.0, R: 2.0}, 2, config(T=1, M=1, margin=0.0), False, None),  # a tie never finalizes
    ({}, 0, config(), False, None),
])
def test_finalization_needs_threshold_voters_margin_and_a_unique_leader(weights, voters, cfg, passes, leader):
    assert _evaluate(weights, voters, cfg) == (passes, leader)


def test_tally_sums_expert_weights_per_verdict():
    reviews = [MagicMock(vote_overall_verdict=v, credibility_weight=w) for v, w in ((F, 2.0), (F, 1.5), (R, 1.0), (None, 9.0))]
    assert _tally(reviews, lambda r: r.vote_overall_verdict) == {F: 3.5, R: 1.0}


def test_review_limits_are_or_ed_and_unset_limits_never_trigger():
    now = datetime(2026, 1, 2, tzinfo=timezone.utc)
    day_old = datetime(2026, 1, 1)  # naive timestamps are UTC
    assert not review_limits_exceeded(config(), votes=99, submitted_at=day_old, now=now)
    assert review_limits_exceeded(config(votes=2), votes=2, submitted_at=now, now=now)
    assert review_limits_exceeded(config(hours=24), votes=0, submitted_at=day_old, now=now)
    assert not review_limits_exceeded(config(votes=5, hours=48), votes=1, submitted_at=day_old, now=now)


# ── voting against a real database ───────────────────────────────────────

async def setup(session, *, kind=SubmissionType.SOURCE_BASED, age_hours=0, **cfg):
    await add_voting_config(session, **cfg)
    admin = await add_user(session, role="admin", full_name="Site Admin")
    experts = [await add_user(session, role="expert") for _ in range(3)]
    if kind == SubmissionType.MULTIMODAL:
        sub, _ = await add_multimodal_submission(session, prediction=MultimodalPredictionLabel.NON_FAKE)
    else:
        sub, _ = await add_completed_submission(session, headline="ঢাকায় আজ ভারী বৃষ্টি", submitter_id=None, submission_type=kind)
    sub.created_at = datetime.now(timezone.utc) - timedelta(hours=age_hours)
    await session.flush()
    return _service(session), admin, experts, sub


async def vote(svc, voter, sub, verdict, *, role="expert", source=None, content=None, date_=None):
    return await svc.submit_vote(sub.id, voter.id, verdict, source, content, date_, WHY, voter_role=role)


async def escalation_notices(session) -> int:
    return (await session.execute(select(func.count()).select_from(Notification)
                                  .where(Notification.notification_type == ESCALATION_NOTIFICATION_TYPE))).scalar_one()


async def test_agreeing_overall_votes_finalize_whatever_the_supplementary_findings(session):
    svc, _, experts, sub = await setup(session, verified_threshold=2.0, min_expert_votes=2, max_review_votes=2)
    first = await vote(svc, experts[0], sub, F, source=SourceStatus.NOT_FOUND)
    assert first.ai_overall_verdict is None and first.ai_source_status == SourceStatus.CONFIRMED  # no AI overall exists
    assert sub.status == SubmissionStatus.EXPERT_REVIEW
    await vote(svc, experts[1], sub, F, source=SourceStatus.CONFIRMED, content=ContentStatus.ALTERED, date_=DateStatus.MISMATCHED)
    assert sub.status == SubmissionStatus.FINALIZED and await escalation_notices(session) == 0

    result = await ResultRepository(session).get_by_submission_id(sub.id)
    assert (result.overall_verdict, result.content_status) == (F, ContentStatus.MATCHED)  # the AI snapshot is untouched
    assert result.final_content_status is None and result.finalized_at
    statuses = (await session.execute(select(ExpertReview.status))).scalars().all()
    assert set(statuses) == {"finalized"}
    profile = (await session.execute(select(ExpertProfile).where(ExpertProfile.user_id == experts[0].id))).scalar_one()
    assert (profile.total_votes, profile.correct_votes) == (1, 1)


async def test_a_split_overall_vote_escalates_at_the_vote_limit_and_notifies_admins_once(session):
    svc, admin, experts, sub = await setup(session, verified_threshold=2.0, min_expert_votes=2, max_review_votes=2)
    same = dict(source=SourceStatus.CONFIRMED, content=ContentStatus.MATCHED, date_=DateStatus.MATCHED)
    await vote(svc, experts[0], sub, F, **same)
    await vote(svc, experts[1], sub, R, **same)  # unanimous supplementary findings do not help
    assert sub.status == SubmissionStatus.ESCALATED and sub.escalated_at
    note = (await session.execute(select(Notification))).scalar_one()
    assert (note.user_id, note.link_url) == (admin.id, f"/admin/review-queue/{sub.id}")
    assert not await svc.reevaluate(sub.id)  # nothing more happens to an escalated claim
    assert await escalation_notices(session) == 1


async def test_the_spec_worked_example_with_tier_weights(session):
    """T=5, M=3, margin 1: Gold 2.0 + Gold 2.0 (Fake) + new 1.0 (Misleading) = 4.0 < T stays open;
    a Silver 1.5 Fake vote makes 5.5 with four voters and a 4.5 lead: Fake."""
    svc, _, experts, sub = await setup(session, kind=SubmissionType.MULTIMODAL, verified_threshold=5.0,
                                       min_expert_votes=3, lead_margin=1.0)
    for verdict, weight in ((F, 2.0), (F, 2.0), (M, 1.0)):
        session.add(ExpertReview(submission_id=sub.id, reviewer_id=uuid.uuid4(), vote_overall_verdict=verdict,
                                 credibility_weight=weight, status="pending"))
    await session.flush()
    assert not await svc.reevaluate(sub.id) and sub.status == SubmissionStatus.EXPERT_REVIEW
    session.add(ExpertReview(submission_id=sub.id, reviewer_id=uuid.uuid4(), vote_overall_verdict=F,
                             credibility_weight=1.5, status="pending"))
    await session.flush()
    assert await svc.reevaluate(sub.id) and sub.status == SubmissionStatus.FINALIZED


async def test_weights_activate_after_n_finalized_votes_and_follow_the_admin_tiers(session):
    svc, _, experts, sub = await setup(session, kind=SubmissionType.MULTIMODAL, activation_threshold_votes=2,
                                       verified_threshold=100.0)
    session.add(CredibilityWeightTier(label="Gold", min_accuracy_pct=50.0, max_accuracy_pct=100.0, weight=2.0, is_active=True))
    session.add_all([
        ExpertProfile(user_id=experts[0].id, total_votes=4, correct_votes=4, completed_reviews_count=4, area_of_expertise="General"),  # Gold
        ExpertProfile(user_id=experts[1].id, total_votes=1, correct_votes=1, completed_reviews_count=1, area_of_expertise="General"),  # below N
        ExpertProfile(user_id=experts[2].id, total_votes=4, correct_votes=1, completed_reviews_count=4, area_of_expertise="General"),  # no tier
    ])
    await session.flush()
    gold = await vote(svc, experts[0], sub, F)
    assert gold.ai_overall_verdict == R  # a NON_FAKE prediction implies Real
    assert [gold.credibility_weight, (await vote(svc, experts[1], sub, F)).credibility_weight,
            (await vote(svc, experts[2], sub, F)).credibility_weight] == [2.0, 1.0, 1.0]


@pytest.mark.parametrize("case", ["own_claim", "second_vote", "finalized", "processing", "inconsistent", "no_ai_result"])
async def test_votes_are_refused_when_they_would_be_unfair_or_incoherent(session, case):
    svc, _, experts, sub = await setup(session)
    expert = experts[0]
    kwargs = {}
    if case == "own_claim":
        sub.submitter_id = expert.id
    elif case == "second_vote":
        await vote(svc, expert, sub, R)
    elif case in ("finalized", "processing"):
        sub.status = SubmissionStatus.FINALIZED if case == "finalized" else SubmissionStatus.PROCESSING
    elif case == "inconsistent":
        kwargs = dict(source=SourceStatus.NOT_FOUND, content=ContentStatus.MATCHED)  # no article, but a headline finding
    elif case == "no_ai_result":
        (await ResultRepository(session).get_by_submission_id(sub.id)).source_status = None
    await session.flush()
    with pytest.raises(DomainValidationError):
        await vote(svc, expert, sub, F, **kwargs)


async def test_multimodal_votes_carry_no_supplementary_findings(session):
    svc, _, experts, sub = await setup(session, kind=SubmissionType.MULTIMODAL)
    with pytest.raises(DomainValidationError):
        await vote(svc, experts[0], sub, F, source=SourceStatus.CONFIRMED)
    (await svc._multimodal.get_by_submission_id(sub.id)).submission_id = uuid.uuid4()  # prediction gone
    await session.flush()
    with pytest.raises(DomainValidationError):
        await vote(svc, experts[1], sub, F)


async def test_an_administrator_decides_only_escalated_claims_and_that_decision_is_final(session):
    svc, admin, experts, sub = await setup(session, verified_threshold=10.0, min_expert_votes=3, max_review_votes=3)
    with pytest.raises(PermissionDeniedError):  # view-only while experts are still voting
        await vote(svc, admin, sub, R, role="admin")
    for expert, verdict in zip(experts, (F, F, R), strict=True):
        await vote(svc, expert, sub, verdict)
    assert sub.status == SubmissionStatus.ESCALATED  # T=10 unreachable
    with pytest.raises(PermissionDeniedError):  # experts can no longer vote
        await vote(svc, await add_user(session, role="expert"), sub, F)

    decision = await vote(svc, admin, sub, M, role="admin")
    assert decision.is_admin_decision and sub.status == SubmissionStatus.FINALIZED
    assert (await ResultRepository(session).get_by_submission_id(sub.id)).overall_verdict == M  # overrides the majority
    profile = (await session.execute(select(ExpertProfile).where(ExpertProfile.user_id == experts[0].id))).scalar_one()
    assert (profile.total_votes, profile.correct_votes) == (1, 0)  # experts scored against the admin
    with pytest.raises(PermissionDeniedError):
        await vote(svc, admin, sub, R, role="admin")
    review_id = (await session.execute(select(ExpertReview.id).where(ExpertReview.reviewer_id == experts[0].id))).scalar_one()
    with pytest.raises(DomainValidationError):  # nobody reopens it
        await svc.edit_vote(review_id, experts[0].id, R, None, None, None, None)


async def test_editing_a_vote_is_owner_only_coherent_and_can_tip_the_decision(session):
    svc, _, experts, sub = await setup(session, verified_threshold=2.0, min_expert_votes=2)
    first = await vote(svc, experts[0], sub, F, source=SourceStatus.CONFIRMED, content=ContentStatus.ALTERED)
    await vote(svc, experts[1], sub, R)
    with pytest.raises(PermissionDeniedError):
        await svc.edit_vote(uuid.UUID(first.id), experts[1].id, R, None, None, None, None)
    edited = await svc.edit_vote(uuid.UUID(first.id), experts[0].id, None, SourceStatus.NOT_FOUND, None, None, "new reason")
    assert (edited.vote_source_status, edited.vote_content_status, edited.justification) == (SourceStatus.NOT_FOUND, None, "new reason")
    assert sub.status == SubmissionStatus.EXPERT_REVIEW
    await svc.edit_vote(uuid.UUID(first.id), experts[0].id, R, None, None, None, None)
    assert sub.status == SubmissionStatus.FINALIZED


async def test_history_stats_and_credibility_reflect_final_decisions_only(session):
    svc, _, experts, sub = await setup(session, verified_threshold=2.0, min_expert_votes=2, activation_threshold_votes=1)
    other, _ = await add_completed_submission(session, headline="অন্য দাবি", submitter_id=None)
    await vote(svc, experts[0], other, F)
    stats = await svc.get_stats(experts[0].id)
    assert (stats.total_votes, stats.accuracy_pct, (await svc.get_credibility(experts[0].id)).score) == (0, None, None)
    await vote(svc, experts[0], sub, R)
    await vote(svc, experts[1], sub, R)  # finalizes `sub` as Real
    history = {h.submission_id: h for h in await svc.get_history(experts[0].id)}
    assert (history[str(sub.id)].final_overall_verdict, history[str(sub.id)].matched) == (R, True)
    assert history[str(other.id)].matched is None  # still open
    assert [h.headline for h in await svc.get_history(experts[0].id, q="অন্য")] == ["অন্য দাবি"]
    stats = await svc.get_stats(experts[0].id)
    assert (stats.total_votes, stats.correct_votes, stats.accuracy_pct) == (1, 1, 100.0)
    assert (await svc.get_credibility(experts[0].id)).score == 1.0


# ── what reviewers see ───────────────────────────────────────────────────

async def test_queues_show_each_role_only_what_it_may_act_on(session):
    svc, admin, experts, open_ = await setup(session)
    escalated, _ = await add_completed_submission(session, headline="জটিল দাবি", submitter_id=None)
    escalated.status, escalated.escalated_at = SubmissionStatus.ESCALATED, datetime.now(timezone.utc)
    own, _ = await add_completed_submission(session, headline="নিজের দাবি", submitter_id=experts[0].id)
    voted, _ = await add_completed_submission(session, headline="ভোট দেওয়া দাবি", submitter_id=None)
    await session.flush()
    await vote(svc, experts[0], voted, F)

    assert [q.submission_id for q in await svc.get_queue(experts[0].id)] == [str(open_.id)]
    with pytest.raises(PermissionDeniedError):
        await svc.get_queue_item(escalated.id, viewer_id=experts[0].id, viewer_role="expert")
    admin_queue = await svc.get_queue(admin.id, viewer_role="admin")
    assert admin_queue[0].submission_id == str(escalated.id) and admin_queue[0].decision_mode == "ADMIN_FINAL"
    assert [q.submission_id for q in await svc.get_queue(admin.id, viewer_role="admin", state="escalated")] == [str(escalated.id)]
    item = await svc.get_queue_item(open_.id, viewer_id=admin.id, viewer_role="admin")
    assert item.can_vote is False and item.decision_mode == "EXPERT_VOTE"
    assert (await svc.get_queue_item(own.id, viewer_id=experts[0].id, viewer_role="expert")).can_vote is False


async def test_queue_search_runs_before_pagination_over_every_open_claim(session):
    svc, _, experts, _ = await setup(session)
    for n in range(105):
        session.add(Submission(submission_type=SubmissionType.SOURCE_BASED, headline=f"Claim {n}", content_hash=str(n),
                               status=SubmissionStatus.EXPERT_REVIEW))
    await session.flush()
    svc._build_queue_item = AsyncMock(side_effect=lambda row, **kw: row.headline)
    found = await svc.get_queue(experts[0].id, q="Claim 0", limit=20)
    assert found[0] == "Claim 0" and len(found) == 20  # exact phrase first, partial matches follow
    assert await svc.get_queue(experts[0].id, q="Claim 104", limit=1) == ["Claim 104"]
    assert len(await svc.get_queue(experts[0].id, offset=100, limit=20)) == 6
    assert await svc.get_queue(experts[0].id, q="not present") == []


async def test_a_queue_item_shows_the_saved_ai_findings_evidence_and_image(session):
    analysis = {
        "headline_alteration": {"status": "COMPLETED", "verdict": "ALTERED", "reason": "numbers differ", "basis": "material_difference",
                                "claim_headline": "সড়ক দুর্ঘটনায় ১০ জন নিহত", "source_title": "সড়ক দুর্ঘটনায় ৫ জন নিহত",
                                "differences": [{"kind": "numbers", "detail": "d", "claim_text": "১০", "source_text": "৫"}]},
        "body_similarity": {"status": "COMPUTED", "jaccard": {"available": True, "value": 0.4}},
    }
    sub, result = await add_completed_submission(session, headline="সড়ক দুর্ঘটনায় ১০ জন নিহত", submitter_id=None, body="বডি " * 200,
                                                 submission_type=SubmissionType.PHOTO_CARD, content_status=ContentStatus.ALTERED,
                                                 analysis_details=analysis)
    article = RetrievedArticle(submission_id=sub.id, url="https://prothomalo.com/a/1", url_hash="u", title="t",
                               body="খ" * 500, rank_score=0.9, extraction_success=True)
    session.add_all([article, PhotocardExtraction(submission_id=sub.id, image_object_key="card.png", status="SUCCEEDED")])
    await session.flush()
    result.top_article_id = article.id
    mm, _ = await add_multimodal_submission(session, prediction=MultimodalPredictionLabel.FAKE)
    storage = MagicMock(get_presigned_url=AsyncMock(side_effect=lambda key: f"https://img/{key}"))
    svc = _service(session)
    svc._photocard_storage = svc._storage = storage

    item = await svc.get_queue_item(sub.id)
    assert item.ai_label == "Relevant article from claimed source: Found · Headline: Altered"
    assert (item.headline_status, item.ai_overall_verdict) == (HeadlineAlterationStatus.ALTERED, None)
    assert item.headline_alteration.differences[0].kind == "numbers" and item.body_similarity.jaccard.value == 0.4
    assert item.top_article.url == article.url and item.top_article.body_snippet.endswith("…")
    assert item.image_url == "https://img/card.png" and len(item.body_text) == len(sub.body_text)
    assert len((await svc.get_queue(uuid.uuid4()))[0].body_text) <= 401  # trimmed in the list

    mm_item = await svc.get_queue_item(mm.id)
    assert (mm_item.ai_label, mm_item.ai_overall_verdict, mm_item.ai_confidence) == ("Likely Fake", F, 0.8)
    assert mm_item.image_url.startswith("https://img/multimodal/")
