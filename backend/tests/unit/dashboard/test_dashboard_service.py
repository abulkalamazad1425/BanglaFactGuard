"""Public statistics, most-claimed sources and the Fact Explorer listing.
An automated check never appears as a final verdict."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

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
from app.features.dashboard.service import DashboardService
from app.features.submissions.models import PhotocardExtraction
from tests.helpers.db import add_completed_submission, add_multimodal_submission


async def test_public_statistics_and_top_sources(session):
    await add_completed_submission(session, headline="এক", submitter_id=None, date_status=DateStatus.MATCHED,
                                   avg_verification_time_ms=1000)
    await add_completed_submission(session, headline="দুই", submitter_id=None, content_status=ContentStatus.ALTERED,
                                   date_status=DateStatus.MISMATCHED, avg_verification_time_ms=3000)
    nf, _ = await add_completed_submission(session, headline="তিন", submitter_id=None, source_status=SourceStatus.NOT_FOUND,
                                           submission_type=SubmissionType.PHOTO_CARD)
    nf.claimed_source_text = "যুগান্তর"
    pending, _ = await add_multimodal_submission(session)
    pending.status = SubmissionStatus.PENDING
    await session.flush()
    svc = DashboardService(session)
    s = await svc.public_stats()
    assert (s.total_submissions, s.pending_count, s.source_confirmed_count, s.source_not_found_count) == (4, 1, 2, 1)
    assert (s.content_matched_count, s.content_altered_count, s.date_matched_count, s.date_mismatched_count) == (1, 1, 1, 1)
    assert (s.method_distribution.source_based, s.method_distribution.multimodal, s.method_distribution.photo_card) == (2, 1, 1)
    assert s.avg_verification_time_seconds == 2.0
    assert [(t.source, t.count) for t in await svc.top_sources(limit=5)] == [("প্রথম আলো", 2), ("যুগান্তর", 1)]


async def test_explorer_rows_show_findings_images_and_only_final_verdicts(session):
    text, _ = await add_completed_submission(session, headline="ঢাকায় বৃষ্টি", submitter_id=None, headline_exact_match=True)
    final, _ = await add_completed_submission(session, headline="চূড়ান্ত দাবি", submitter_id=None, overall_verdict=OverallVerdict.FAKE)
    final.status = SubmissionStatus.FINALIZED
    card, _ = await add_completed_submission(session, headline="কার্ড", submitter_id=None, submission_type=SubmissionType.PHOTO_CARD)
    session.add(PhotocardExtraction(submission_id=card.id, image_object_key="card.png", status="SUCCEEDED"))
    mm, _ = await add_multimodal_submission(session, prediction=MultimodalPredictionLabel.NON_FAKE)
    await session.flush()
    storage = MagicMock(get_presigned_url=AsyncMock(side_effect=lambda key: f"https://img/{key}"))
    svc = DashboardService(session, multimodal_storage=storage, photocard_storage=storage)
    page = await svc.explorer(keyword=None, source_status=None, content_status=None, date_status=None,
                              overall_verdict=None, method=None, date_from=None, date_to=None, source_id=None,
                              review_state=None, limit=10, offset=0)
    rows = {i.submission_id: i for i in page.items}
    assert page.total == 4 and page.archive_summary == {"total": 4, "finalized": 1, "review": 3}
    t = rows[str(text.id)]
    assert (t.overall_verdict, t.is_finalized, t.headline_status) == (None, False, HeadlineAlterationStatus.EXACT_MATCHED)
    assert (rows[str(final.id)].overall_verdict, rows[str(final.id)].is_finalized) == (OverallVerdict.FAKE, True)
    assert rows[str(card.id)].image_url == "https://img/card.png"
    m = rows[str(mm.id)]
    assert (m.prediction, m.overall_verdict, m.confidence, m.claimed_source_text) == (
        MultimodalPredictionLabel.NON_FAKE, None, 0.8, None,
    )
    assert m.image_url.startswith("https://img/multimodal/")
