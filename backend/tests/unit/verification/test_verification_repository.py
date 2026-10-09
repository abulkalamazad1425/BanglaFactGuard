"""The automated result is written once per submission (upsert), and each
execution's own timings are recorded on it."""

from app.core.constants import ContentStatus, SourceStatus
from app.features.verification.repository import ResultRepository
from tests.helpers.db import add_completed_submission


async def test_upsert_keeps_one_row_and_timings_describe_this_execution(session):
    sub, _ = await add_completed_submission(session, headline="h", submitter_id=None)
    repo = ResultRepository(session)
    updated = await repo.upsert_result(sub.id, source_status=SourceStatus.CONFIRMED, content_status=ContentStatus.ALTERED,
                                       date_status=None, confidence=0.5, reasoning="new", analysis_details={"metrics": {}})
    assert updated.content_status == ContentStatus.ALTERED and (await repo.get_by_submission_id(sub.id)).id == updated.id

    await repo.record_timings(sub.id, stage_ms={"s01_normalizer": 3}, pipeline_ms=42, cache_hit=True)
    result = await repo.get_by_submission_id(sub.id)
    assert result.avg_verification_time_ms == 42 and result.analysis_details["metrics"] == {}
    assert result.analysis_details["timings"] == {"stage_ms": {"s01_normalizer": 3}, "preprocessing_ms": {},
                                                  "pipeline_ms": 42, "cache_hit": True}
    other, res = await add_completed_submission(session, headline="h2", submitter_id=None)
    await session.delete(res)
    await repo.record_timings(other.id, stage_ms={}, pipeline_ms=1)  # nothing stored yet: no-op
