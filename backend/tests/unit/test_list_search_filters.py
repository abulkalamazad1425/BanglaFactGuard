"""Search/filter on My Submissions, Expert Management and Source Management,
and the profile's submission total (counted live, not from a cached counter)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import ARRAY
from sqlalchemy.ext.compiler import compiles

from app.core.constants import SubmissionStatus, SubmissionType
from app.features.admin.service import AdminService
from app.features.auth.repository import UserRepository
from app.features.expert_review.models import ExpertProfile
from app.features.multimodal.models import MultimodalAnalysis
from app.features.sources.repository import SourceRepository
from app.features.sources.service import SourceService
from app.features.users.service import UserAccountService
from tests.unit.db_helpers import add_completed_submission, add_source, add_user, make_session_factory


@compiles(ARRAY, "sqlite")
def _array_sqlite(type_, compiler, **kw):
    return "JSON"


@pytest.fixture
async def session():
    engine, factory = await make_session_factory()
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: MultimodalAnalysis.__table__.create(c))
        await conn.run_sync(lambda c: ExpertProfile.__table__.create(c))
    s = factory()
    yield s
    await s.close()
    await engine.dispose()


async def _mine(session, user, headline, status, *, kind=SubmissionType.SOURCE_BASED, duplicate_of=None):
    sub, _ = await add_completed_submission(session, headline=headline, submitter_id=user.id, submission_type=kind)
    sub.status = status
    sub.duplicate_of_submission_id = duplicate_of
    await session.flush()
    return sub


async def test_my_submissions_search_and_filters(session):
    me = await add_user(session)
    other = await add_user(session)
    final = await _mine(session, me, "ঢাকায় মেট্রোরেল চালু", SubmissionStatus.FINALIZED)
    review = await _mine(session, me, "বন্যায় ক্ষতিগ্রস্ত কৃষক", SubmissionStatus.EXPERT_REVIEW)
    running = await _mine(session, me, "ঢাকায় বাস ভাড়া বাড়ল", SubmissionStatus.PROCESSING,
                          kind=SubmissionType.PHOTO_CARD)
    failed = await _mine(session, me, "নির্বাচন কমিশনের বৈঠক", SubmissionStatus.FAILED)
    # Re-submitted copy of a finalized claim: stored EXPERT_REVIEW, shown (and filtered) as final.
    dup = await _mine(session, me, "ঢাকায় মেট্রোরেল চালু", SubmissionStatus.EXPERT_REVIEW, duplicate_of=final.id)
    await _mine(session, other, "ঢাকায় অন্য কারও দাবি", SubmissionStatus.FINALIZED)
    svc = UserAccountService(session)

    async def ids(**kw):
        return {r.submission_id for r in await svc.my_submissions(me, limit=50, offset=0, **kw)}

    assert await ids() == {str(s.id) for s in (final, review, running, failed, dup)}
    assert await ids(state="final") == {str(final.id), str(dup.id)}
    assert await ids(state="review") == {str(review.id)}
    assert await ids(state="in_progress") == {str(running.id)}
    assert await ids(state="failed") == {str(failed.id)}
    assert await ids(submission_type=SubmissionType.PHOTO_CARD) == {str(running.id)}
    assert await ids(q="ঢাকায়") == {str(final.id), str(running.id), str(dup.id)}  # never another user's
    assert await ids(q="ঢাকায়", state="in_progress") == {str(running.id)}
    assert await ids(q="অনুপস্থিত") == set()


async def test_profile_counts_submissions_live_not_from_the_cached_counter(session):
    me = await add_user(session)
    me.total_submissions = 1  # the drifted counter
    for i in range(3):
        await _mine(session, me, f"দাবি {i}", SubmissionStatus.EXPERT_REVIEW, kind=SubmissionType.PHOTO_CARD)
    await _mine(session, me, "ব্যর্থ দাবি", SubmissionStatus.FAILED)
    assert (await UserAccountService(session).profile(me)).total_submissions == 4


async def test_expert_management_search(session):
    a = await add_user(session, role="expert")
    a.full_name, a.email = "Newton Sir", "newton@example.com"
    b = await add_user(session, role="expert")
    b.full_name, b.email = "Rahima Begum", "rahima@iit.example.com"
    session.add(ExpertProfile(user_id=b.id, area_of_expertise="রাজনীতি", total_votes=0, correct_votes=0,
                              completed_reviews_count=0))
    await add_user(session, role="user")  # never listed
    await session.flush()
    svc = AdminService(session=session, user_repo=UserRepository(session), profile_repo=AsyncMock(),
                       tier_repo=AsyncMock(), token_repo=AsyncMock())
    svc._profiles.get_by_user_id.return_value = None

    async def emails(q=None):
        return [e.email for e in await svc.list_experts(q=q)]

    assert sorted(await emails()) == ["newton@example.com", "rahima@iit.example.com"]
    assert await emails("newton") == ["newton@example.com"]
    assert await emails("iit") == ["rahima@iit.example.com"]
    assert await emails("রাজনীতি") == ["rahima@iit.example.com"]  # expertise area
    assert await emails("zzqq") == []


async def test_source_management_search_has_a_matching_total(session):
    await add_source(session, "prothomalo.com")
    star = await add_source(session, "bangla.thedailystar.net")
    star.display_name, star.aliases = "দ্য ডেইলি স্টার", ["daily star"]
    inactive = await add_source(session, "jugantor.com")
    inactive.display_name, inactive.is_active = "যুগান্তর", False
    await session.flush()
    svc = SourceService(SourceRepository(session))

    res = await svc.list_sources(include_inactive=True, q="ডেইলি", size=10)
    assert res.total == 1 and res.items[0].canonical_name == "bangla.thedailystar.net"
    res = await svc.list_sources(include_inactive=True, q="daily star", size=10)
    assert res.items[0].canonical_name == "bangla.thedailystar.net"
    assert (await svc.list_sources(include_inactive=True, q="যুগান্তর", size=10)).total == 1
    assert (await svc.list_sources(include_inactive=False, q="যুগান্তর", size=10)).total == 0
    assert (await svc.list_sources(include_inactive=True, q="zzqq", size=10)).total == 0
    assert (await svc.list_sources(include_inactive=True, size=10)).total == 3  # no query: unchanged
