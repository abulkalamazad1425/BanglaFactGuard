from types import SimpleNamespace
from unittest.mock import AsyncMock
import uuid

import pytest

from app.core.constants import OverallVerdict, SubmissionStatus, SubmissionType
from app.features.expert_review.models import ExpertProfile, ExpertReview, CredibilityWeightTier, VotingConfig
from app.features.expert_review.repository import ExpertProfileRepository
from app.features.submissions.models import Submission
from app.shared.models_registry import Base
from tests.unit.db_helpers import make_session_factory, add_user
from tests.unit.test_expert_review_finalize import _make_service, _review, _config


async def test_new_profile_has_no_score_even_if_legacy_initial_score_is_passed():
    engine, factory = await make_session_factory()
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=[ExpertProfile.__table__]))
    async with factory() as session:
        user = await add_user(session, role='expert')
        profile = await ExpertProfileRepository(session).get_or_create(user.id, initial_score=.5)
        assert profile.credibility_score is None
        assert profile.total_votes == 0
    await engine.dispose()


async def test_zero_completed_votes_have_neutral_weight_even_when_N_is_zero():
    ctx = _make_service()
    weight, tier = await ctx['svc']._resolve_weight(SimpleNamespace(total_votes=0, correct_votes=0), _config(N=0))
    assert weight == 1 and tier is None


async def test_queue_search_is_before_pagination_and_not_limited_to_latest_100():
    engine, factory = await make_session_factory()
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=[CredibilityWeightTier.__table__, ExpertReview.__table__]))
    async with factory() as session:
        user = await add_user(session, role='expert')
        ids = []
        for n in range(105):
            row = Submission(id=uuid.uuid4(), submission_type=SubmissionType.SOURCE_BASED,
                             headline=f'Claim {n}', claimed_source_text='Outlet', content_hash=str(n),
                             status=SubmissionStatus.EXPERT_REVIEW)
            session.add(row)
            ids.append(row.id)
        await session.flush()
        ctx = _make_service()
        ctx['svc']._session = session
        ctx['svc']._build_queue_item = AsyncMock(side_effect=lambda row, **kw: row.headline)
        # Keyword search (OR): partial matches are included, the exact phrase ranks first.
        found = await ctx['svc'].get_queue(user.id, q='Claim 0', limit=20)
        assert found[0] == 'Claim 0' and len(found) == 20
        assert await ctx['svc'].get_queue(user.id, q='Claim 104', limit=1) == ['Claim 104']
        assert len(await ctx['svc'].get_queue(user.id, offset=100, limit=20)) == 5
        assert await ctx['svc'].get_queue(user.id, q='not present') == []
    await engine.dispose()
