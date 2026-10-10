"""Expert account management, platform statistics, credibility tiers that
must tile 0-100% exactly, and voting configuration."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.core.constants import SubmissionStatus
from app.core.exceptions import (
    DomainValidationError,
    DuplicateRecordError,
    RecordNotFoundError,
    WeakPasswordError,
)
from app.features.admin.schemas import (
    CreateExpertRequest,
    CredibilityWeightTierItem,
    CredibilityWeightTierRequest,
    CredibilityWeightTierSetRequest,
    CredibilityWeightTierUpdateRequest,
    ResetExpertPasswordRequest,
    UpdateExpertRequest,
    VotingConfigUpdateRequest,
)
from app.features.admin.service import AdminService
from app.features.auth import security
from app.features.auth.models import RefreshToken
from app.features.auth.repository import RefreshTokenRepository, UserRepository
from app.features.expert_review.models import CredibilityWeightTier, ExpertProfile
from app.features.expert_review.repository import (
    CredibilityWeightTierRepository,
    ExpertProfileRepository,
)
from tests.helpers.db import add_completed_submission, add_user


@pytest.fixture(autouse=True)
def fast_bcrypt(monkeypatch):
    monkeypatch.setattr(security._AUTH, "bcrypt_rounds", 4)


@pytest.fixture
def admin(session) -> AdminService:
    return AdminService(session, UserRepository(session), ExpertProfileRepository(session),
                        CredibilityWeightTierRepository(session), RefreshTokenRepository(session))


def new_expert(email="expert@example.com", **kw) -> CreateExpertRequest:
    return CreateExpertRequest(**{"full_name": "Newton Sir", "email": email, "password": "Secret123", **kw})


async def test_expert_accounts_are_created_found_updated_and_switched_off(admin, session):
    with pytest.raises(WeakPasswordError):
        await admin.create_expert(new_expert(password="weakpassword"))
    created = await admin.create_expert(new_expert(expertise_area="রাজনীতি"))
    assert (created.role, created.expertise_area, created.credibility_score) == ("expert", "রাজনীতি", None)
    with pytest.raises(DuplicateRecordError):
        await admin.create_expert(new_expert())
    other = await admin.create_expert(new_expert("rahima@iit.example.com", full_name="Rahima Begum"))
    plain_user = await add_user(session)

    expert_id = uuid.UUID(created.id)
    updated = await admin.update_expert(expert_id, UpdateExpertRequest(full_name="Dr. Newton", expertise_area="অর্থনীতি"))
    assert (updated.full_name, updated.expertise_area) == ("Dr. Newton", "অর্থনীতি")
    with pytest.raises(DuplicateRecordError):
        await admin.update_expert(expert_id, UpdateExpertRequest(email=other.email))
    with pytest.raises(RecordNotFoundError):
        await admin.get_expert(plain_user.id)

    session.add(RefreshToken(user_id=expert_id, token_hash="h", expires_at=security.create_refresh_token()[2]))
    await session.flush()
    assert (await admin.deactivate_expert(expert_id)).is_active is False
    assert (await session.execute(select(RefreshToken.revoked))).scalar_one() is True  # signed out at once
    assert (await admin.activate_expert(expert_id)).is_active is True


async def test_expert_search_covers_name_email_and_expertise(admin, session):
    await admin.create_expert(new_expert("newton@example.com"))
    await admin.create_expert(new_expert("rahima@iit.example.com", full_name="Rahima Begum", expertise_area="রাজনীতি"))
    await add_user(session)  # never listed

    async def emails(q=None):
        return sorted(e.email for e in await admin.list_experts(q=q))

    assert await emails() == ["newton@example.com", "rahima@iit.example.com"]
    assert await emails("newton") == ["newton@example.com"]
    assert await emails("iit") == await emails("রাজনীতি") == ["rahima@iit.example.com"]
    assert await emails("zzqq") == []


async def test_resetting_a_password_ends_the_experts_sessions(admin, session):
    created = await admin.create_expert(new_expert())
    expert_id = uuid.UUID(created.id)
    session.add(RefreshToken(user_id=expert_id, token_hash="h", expires_at=security.create_refresh_token()[2]))
    await session.flush()
    await admin.reset_expert_password(expert_id, ResetExpertPasswordRequest(new_password="NewSecret1"))
    user = await UserRepository(session).get_by_id(expert_id)
    assert security.verify_password("NewSecret1", user.hashed_password)
    assert (await session.execute(select(RefreshToken.revoked))).scalar_one() is True
    with pytest.raises(RecordNotFoundError):
        await admin.reset_expert_password((await add_user(session)).id, ResetExpertPasswordRequest(new_password="NewSecret1"))


async def test_platform_statistics_count_only_original_claims(admin, session):
    await admin.create_expert(new_expert())
    await add_user(session, role="expert", is_active=False)
    open_, _ = await add_completed_submission(session, headline="এক", submitter_id=None, avg_verification_time_ms=2000)
    escalated, _ = await add_completed_submission(session, headline="দুই", submitter_id=None, avg_verification_time_ms=4000)
    escalated.status = SubmissionStatus.ESCALATED
    copy, _ = await add_completed_submission(session, headline="এক", submitter_id=None)
    copy.duplicate_of_submission_id = open_.id
    await session.flush()
    stats = await admin.get_platform_stats()
    assert (stats.total_submissions, stats.pending_expert_reviews, stats.escalated_claims) == (3, 1, 1)
    assert (stats.total_experts, stats.active_experts, stats.avg_verification_time_seconds) == (2, 1, 3.0)


def tier(label, lo, hi, *, weight=1.0, active=True):
    return CredibilityWeightTierRequest(label=label, min_accuracy_pct=lo, max_accuracy_pct=hi, weight=weight, is_active=active)


def item(label, lo, hi, *, weight=1.0, active=True, id=None):
    """One row of a whole-set save."""
    return CredibilityWeightTierItem(id=id, label=label, min_accuracy_pct=lo, max_accuracy_pct=hi, weight=weight,
                                     is_active=active)


@pytest.fixture
async def seeded(session):
    """The tiers the migration seeds."""
    ids = {}
    for label, lo, hi, w in (("Novice", 0, 40, 0.5), ("Competent", 40, 70, 1.0), ("Expert", 70, 90, 1.5), ("Master", 90, 100, 2.0)):
        row = CredibilityWeightTier(label=label, min_accuracy_pct=lo, max_accuracy_pct=hi, weight=w, is_active=True)
        session.add(row)
        await session.flush()
        ids[label] = row.id
    return ids


async def active(admin) -> list[tuple]:
    return [(t.label, t.min_accuracy_pct, t.max_accuracy_pct, t.weight)
            for t in await admin.list_credibility_tiers() if t.is_active]


async def test_single_tier_changes_never_leave_a_gap_or_an_overlap(admin, seeded):
    for bad in (tier("Upside", 50, 40), tier("Overlap", 30, 50)):
        with pytest.raises(DomainValidationError):
            await admin.create_credibility_tier(bad)
    draft = await admin.create_credibility_tier(tier("Draft", 30, 50, active=False))  # inactive tiers are not tiled
    await admin.update_credibility_tier(uuid.UUID(draft.id), CredibilityWeightTierUpdateRequest(weight=9.0))
    for label, change in (("Competent", dict(max_accuracy_pct=75)),   # overlaps Expert
                          ("Novice", dict(min_accuracy_pct=10)),      # no longer starts at 0
                          ("Master", dict(max_accuracy_pct=95)),      # no longer ends at 100
                          ("Expert", dict(is_active=False))):         # deactivating leaves a gap
        with pytest.raises(DomainValidationError):
            await admin.update_credibility_tier(seeded[label], CredibilityWeightTierUpdateRequest(**change))
    with pytest.raises(DomainValidationError):  # deleting an active tier leaves a gap
        await admin.delete_credibility_tier(seeded["Expert"])
    assert (await admin.update_credibility_tier(seeded["Master"], CredibilityWeightTierUpdateRequest(weight=3.0))).weight == 3.0
    await admin.delete_credibility_tier(uuid.UUID(draft.id))
    assert len(await active(admin)) == 4
    for call in (admin.delete_credibility_tier(uuid.uuid4()),
                 admin.update_credibility_tier(uuid.uuid4(), CredibilityWeightTierUpdateRequest())):
        with pytest.raises(RecordNotFoundError):
            await call


async def test_saving_the_whole_set_can_split_merge_and_rebound_tiers(admin, seeded):
    # split Master into two, merge Novice+Competent, keep Expert: impossible one tier at a time
    saved = await admin.replace_credibility_tiers(CredibilityWeightTierSetRequest(tiers=[
        item("Learner", 0, 70, weight=0.75, id=seeded["Novice"]),
        item("Expert", 70, 90, weight=1.5, id=seeded["Expert"]),
        item("Master", 90, 95, weight=2.0, id=seeded["Master"]),
        item("Grandmaster", 95, 100, weight=3.0),
        item("Retired", 0, 100, active=False),
    ]))
    assert await active(admin) == [("Learner", 0, 70, 0.75), ("Expert", 70, 90, 1.5),
                                   ("Master", 90, 95, 2.0), ("Grandmaster", 95, 100, 3.0)]
    assert len(saved) == 5 and seeded["Competent"] not in {uuid.UUID(t.id) for t in saved}  # left out -> deleted
    resolved = await CredibilityWeightTierRepository(admin._session).resolve_tier_for_accuracy(97.0)
    assert resolved.label == "Grandmaster"


@pytest.mark.parametrize("tiers,error", [
    ([item("A", 0, 60), item("B", 70, 100)], DomainValidationError),            # gap
    ([item("A", 0, 60), item("B", 50, 100)], DomainValidationError),            # overlap
    ([item("A", 5, 100)], DomainValidationError),                               # does not start at 0
    ([item("A", 0, 90)], DomainValidationError),                                # does not end at 100
    ([item("A", 0, 100, active=False)], DomainValidationError),                 # no active tier at all
    ([item("A", 0, 100), item("B", 50, 40, active=False)], DomainValidationError),  # invalid range, even inactive
    ([item("A", 0, 100, id=uuid.uuid4())], RecordNotFoundError),                # unknown tier
])
async def test_an_invalid_set_is_rejected_and_nothing_changes(admin, seeded, tiers, error):
    before = await active(admin)
    with pytest.raises(error):
        await admin.replace_credibility_tiers(CredibilityWeightTierSetRequest(tiers=tiers))
    assert await active(admin) == before


async def test_a_tier_cannot_be_listed_twice(admin, seeded):
    same = seeded["Novice"]
    with pytest.raises(DomainValidationError):
        await admin.replace_credibility_tiers(CredibilityWeightTierSetRequest(tiers=[
            item("A", 0, 50, id=same), item("B", 50, 100, id=same),
        ]))


async def test_changing_n_rescores_every_expert_at_once(admin, session):
    expert = await add_user(session, role="expert")
    session.add(ExpertProfile(user_id=expert.id, area_of_expertise="General", total_votes=4, correct_votes=3,
                              completed_reviews_count=4))
    await session.flush()
    assert (await admin.get_voting_config()).activation_threshold_votes == 10
    config = await admin.update_voting_config(VotingConfigUpdateRequest(activation_threshold_votes=4, max_review_hours=48))
    assert (config.activation_threshold_votes, config.max_review_hours) == (4, 48)
    profile = (await session.execute(select(ExpertProfile))).scalar_one()
    await session.refresh(profile)
    assert profile.credibility_score == 0.75
    await admin.update_voting_config(VotingConfigUpdateRequest(activation_threshold_votes=5))
    await session.refresh(profile)
    assert profile.credibility_score is None
