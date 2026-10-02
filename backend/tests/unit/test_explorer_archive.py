from datetime import date, datetime, timezone

import pytest
from sqlalchemy import ARRAY
from sqlalchemy.ext.compiler import compiles

from app.core.constants import ContentStatus, OverallVerdict, SubmissionStatus, SubmissionType, MultimodalPredictionLabel
from app.features.multimodal.models import MultimodalAnalysis
from app.features.submissions.repository import SubmissionRepository
from tests.unit.db_helpers import add_completed_submission, make_session_factory


@compiles(ARRAY, 'sqlite')
def array_sqlite(type_, compiler, **kw):
    return 'JSON'


@pytest.mark.asyncio
async def test_archive_counts_and_review_filters_share_scope():
    engine, factory = await make_session_factory()
    try:
        async with engine.begin() as conn:
            await conn.run_sync(lambda c: MultimodalAnalysis.__table__.create(c))
        async with factory() as session:
            final, _ = await add_completed_submission(session, headline='Final', submitter_id=None, overall_verdict=OverallVerdict.REAL)
            review, _ = await add_completed_submission(session, headline='Review', submitter_id=None)
            duplicate, _ = await add_completed_submission(session, headline='Repeat', submitter_id=None)
            duplicate.duplicate_of_submission_id = review.id
            failed, _ = await add_completed_submission(session, headline='Failed', submitter_id=None)
            failed.status = SubmissionStatus.FAILED
            mm, _ = await add_completed_submission(session, headline='Image', submitter_id=None, submission_type=SubmissionType.MULTIMODAL)
            session.add(MultimodalAnalysis(submission_id=mm.id, image_object_key='test.png', model_version='test', prediction=MultimodalPredictionLabel.NON_FAKE, confidence_fake=0.1, confidence_real=0.9))
            await session.flush()
            repo = SubmissionRepository(session)
            assert await repo.explorer_summary() == {'total': 3, 'finalized': 1, 'review': 2}
            rows, total = await repo.search(review_state='finalized')
            assert total == 1 and rows[0].id == final.id
            rows, total = await repo.search(review_state='review')
            assert total == 2 and {r.id for r in rows} == {review.id, mm.id}
            rows, total = await repo.search(overall_verdict=OverallVerdict.REAL)
            assert total == 1  # A preliminary NON_FAKE prediction is never final REAL.
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_archive_dates_include_end_day_and_filters_use_reviewed_findings():
    engine, factory = await make_session_factory()
    try:
        async with engine.begin() as conn:
            await conn.run_sync(lambda c: MultimodalAnalysis.__table__.create(c))
        async with factory() as session:
            sub, _ = await add_completed_submission(session, headline='Corrected', submitter_id=None, content_status=ContentStatus.MATCHED, final_content_status=ContentStatus.ALTERED, overall_verdict=OverallVerdict.ALTERED)
            sub.created_at = datetime(2026, 10, 2, 23, 59, tzinfo=timezone.utc)
            later, _ = await add_completed_submission(session, headline='Tomorrow', submitter_id=None)
            later.created_at = datetime(2026, 10, 3, 0, 0, tzinfo=timezone.utc)
            await session.flush()
            repo = SubmissionRepository(session)
            rows, total = await repo.search(date_from=date(2026, 10, 2), date_to=date(2026, 10, 2), content_status=ContentStatus.ALTERED)
            assert total == 1 and rows[0].id == sub.id
            _, total = await repo.search(date_to=date(2026, 10, 2), content_status=ContentStatus.MATCHED)
            assert total == 0
            _, total = await repo.search(date_to=date(2026, 10, 2), review_state='review')
            assert total == 0
    finally:
        await engine.dispose()
