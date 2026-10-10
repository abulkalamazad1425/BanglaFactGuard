"""Photo cards: accepted image-only and durably, read by Gemini once, the
card's values become a headline-only claim run through the shared pipeline,
and failures stop before verification with their own message."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import func, select

from app.core.constants import ClaimScope, SubmissionStatus, SubmissionType
from app.core.exceptions import ImageStorageUnavailableError, PermanentJobError
from app.features.notifications.models import Notification
from app.features.photocard.claim_extraction import (
    API_FAILURE_MESSAGE,
    INVALID_CONTENT_MESSAGE,
    STATUS_API_FAILED,
    STATUS_INVALID_CONTENT,
    STATUS_SUCCEEDED,
    CardExtraction,
)
from app.features.photocard.service import PhotoCardService, extraction_failures
from app.features.photocard.verification_stages import compute_photocard_hash
from app.features.sources.repository import SourceRepository
from app.features.submissions.models import Submission
from app.features.submissions.repository import (
    PhotocardExtractionRepository,
    RetrievedArticleRepository,
    SubmissionRepository,
)
from app.features.verification.job_repository import VerificationJobRepository
from app.features.verification.pipeline.stages.s13_result_persistence import ResultPersistenceStage
from app.features.verification.repository import ResultRepository
from tests.helpers.db import add_completed_submission, add_source, add_user
from tests.helpers.pipeline import article, make_context, run_analysis

HEADLINE = "সরকার নতুন সেতু উদ্বোধন করেছে"
CARD_DATE = date(2026, 6, 7)


def storage(upload_ok=True, image=b"image-bytes") -> MagicMock:
    return MagicMock(build_object_key=lambda sid, name: f"photocard/{sid}/{name}", upload=AsyncMock(return_value=upload_ok),
                     download=AsyncMock(return_value=image), get_presigned_url=AsyncMock(return_value="https://minio/card.png"))


class FakeExtractor:
    """Stands in for Gemini; `result` may be a callable taking the source repo."""

    result = None
    calls = 0

    def __init__(self, *, source_repo, http_client, **_):
        self.source_repo = source_repo

    async def extract(self, image_bytes):
        FakeExtractor.calls += 1
        r = FakeExtractor.result
        return await r(self.source_repo) if callable(r) else r


def extraction(source=None, *, status=STATUS_SUCCEEDED, published=CARD_DATE, **kw) -> CardExtraction:
    ok = status == STATUS_SUCCEEDED
    values = dict(status=status, headline=HEADLINE if ok else None, source=source if ok else None,
                  published_date=published if ok else None, attempts=1, model_version="gemini-test",
                  details={"model": "gemini-test", "attempts": [{"attempt": 1, "outcome": "success"}]},
                  timings_ms={"gemini_extraction": 5})
    values.update(kw)
    return CardExtraction(**values)


async def with_source(source_repo, published=CARD_DATE):
    [src] = await source_repo.list_active()
    return extraction(src, published=published)


class FakeOrchestrator:
    """The shared pipeline over deterministic fakes: real analysis (S08-S12)
    and the REAL persistence stage. `cache_hit_from` simulates an S02 hit."""

    captured: dict = {}
    cache_hit_from = None
    crash = False

    def __init__(self, *, stages=None, submission_repo=None):
        self.repo = submission_repo

    async def run(self, context):
        FakeOrchestrator.captured["context"] = context
        if FakeOrchestrator.crash:
            raise RuntimeError("pipeline crashed")
        if FakeOrchestrator.cache_hit_from:
            context.cache_hit, context.reused_from_submission_id = True, FakeOrchestrator.cache_hit_from
            return context
        ctx = make_context(context.raw_headline, scope=context.claim_scope, published_date=context.published_date,
                           top=article(context.raw_headline, context.raw_headline + "।", published=context.published_date))
        ctx.submission_id, ctx.submitter_id = context.submission_id, context.submitter_id
        ctx.content_hash = (await self.repo.get_by_id(context.submission_id)).content_hash  # what the card S01 computes
        ctx = await run_analysis(ctx)
        session = self.repo.session
        return await ResultPersistenceStage(self.repo, ResultRepository(session), RetrievedArticleRepository(session),
                                           MagicMock(set_claim_pointer=AsyncMock()), session=session).execute(ctx)


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    FakeOrchestrator.captured, FakeOrchestrator.cache_hit_from, FakeOrchestrator.crash = {}, None, False
    FakeExtractor.result, FakeExtractor.calls = with_source, 0
    monkeypatch.setattr("app.features.photocard.service.PipelineOrchestrator", FakeOrchestrator)
    monkeypatch.setattr("app.features.photocard.service.build_photocard_stages", lambda **kw: [])
    monkeypatch.setattr("app.features.photocard.service.PhotocardClaimExtractor", FakeExtractor)


@pytest.fixture
async def session(session):
    await add_source(session)
    await session.commit()
    return session


def service(session, store=None) -> PhotoCardService:
    return PhotoCardService(
        storage=store or storage(), submission_repo=SubmissionRepository(session),
        extraction_repo=PhotocardExtractionRepository(session), result_repo=ResultRepository(session),
        article_repo=RetrievedArticleRepository(session), source_repo=SourceRepository(session),
        cache_service=MagicMock(), embedding_service=MagicMock(), ner_service=MagicMock(), nli_service=MagicMock(),
        http_client=MagicMock(),
    )


async def accept(session, user_id=None, svc=None):
    svc = svc or service(session)
    return svc, await svc.accept_upload(image_bytes=b"img", original_filename="card.png", submitter_id=user_id)


async def test_acceptance_stores_only_the_image_with_an_owned_submission_and_a_job(db, session):
    user = await add_user(session)
    svc, sub = await accept(session, user.id)
    assert svc.storage.upload.await_count == 1
    async with db() as fresh:  # committed before the 202
        row = await SubmissionRepository(fresh).get_by_id(sub.id)
        rec = await PhotocardExtractionRepository(fresh).get_by_submission_id(sub.id)
        job = await VerificationJobRepository(fresh).get_by_submission(sub.id)
    assert (row.submission_type, row.submitter_id, row.status, row.processing_phase) == (
        SubmissionType.PHOTO_CARD, user.id, SubmissionStatus.PENDING, "QUEUED",
    )
    assert row.headline is None and row.claimed_source_text is None and row.published_date is None  # unknown until read
    assert rec.image_object_key.endswith("card.png") and rec.status == "PENDING"
    assert (job.kind, job.payload) == ("PHOTO_CARD", {})
    assert "My Submissions" in svc.accepted_response(row).message
    anonymous = SimpleNamespace(id=uuid.uuid4(), status=SubmissionStatus.PENDING, processing_phase="QUEUED",
                                submitter_id=None, created_at=datetime.now(timezone.utc))
    assert "keep the result link" in svc.accepted_response(anonymous).message


async def test_an_image_that_could_not_be_stored_is_not_accepted(session):
    with pytest.raises(ImageStorageUnavailableError):
        await accept(session, svc=service(session, storage(upload_ok=False)))
    assert (await session.execute(select(func.count()).select_from(Submission))).scalar_one() == 0


async def test_the_read_card_becomes_a_saved_headline_only_result(session):
    user = await add_user(session)
    _, sub = await accept(session, user.id)
    await service(session).process_submission(sub.id)
    ctx = FakeOrchestrator.captured["context"]
    assert (ctx.raw_claimed_source, ctx.published_date, ctx.claim_scope, ctx.raw_news_body) == (
        "prothomalo.com", CARD_DATE, ClaimScope.HEADLINE_ONLY, None,
    )
    row = await SubmissionRepository(session).get_by_id(sub.id)
    assert (row.status, row.headline, row.claimed_source_text, row.published_date) == (
        SubmissionStatus.EXPERT_REVIEW, HEADLINE, "prothomalo.com", CARD_DATE,
    )
    assert row.content_hash == compute_photocard_hash(HEADLINE, "prothomalo.com", published_date=CARD_DATE)
    res = await ResultRepository(session).get_by_submission_id(sub.id)
    assert set(res.analysis_details["timings"]["preprocessing_ms"]) == {"image_download", "gemini_extraction"}
    notes = (await session.execute(select(Notification).where(Notification.user_id == user.id))).scalars().all()
    assert [n.link_url for n in notes] == [f"/verify/{sub.id}"]

    detail = await service(session).get_result(sub.id)
    assert (detail.headline, detail.claimed_source_name, detail.published_date, detail.extraction_status) == (
        HEADLINE, "প্রথম আলো", CARD_DATE, STATUS_SUCCEEDED,
    )
    assert detail.image_url and detail.verification.overall_verdict is None and detail.verification.review_pending
    await service(session).process_submission(sub.id)  # a finished card is never re-processed
    assert FakeExtractor.calls == 1


@pytest.mark.parametrize("status,code,message", [
    (STATUS_API_FAILED, "gemini_unavailable", API_FAILURE_MESSAGE),
    (STATUS_INVALID_CONTENT, "source_not_identified", INVALID_CONTENT_MESSAGE),
])
async def test_a_failed_reading_stops_before_verification_with_its_own_message(session, monkeypatch, status, code, message):
    from app.features.verification import source_policy

    monkeypatch.setattr(source_policy, "fallback_enabled", lambda: False)
    attempts = [{"attempt": i, "outcome": "timeout"} for i in range(1, 10)] if status == STATUS_API_FAILED else []
    FakeExtractor.result = extraction(status=status, failure_code=code, attempts=len(attempts) or 1,
                                      details={"attempts": attempts})
    _, sub = await accept(session)
    with pytest.raises(PermanentJobError) as failed:
        await service(session).process_submission(sub.id)
    assert failed.value.reason == message and "context" not in FakeOrchestrator.captured  # no verification ran
    rec = await PhotocardExtractionRepository(session).get_by_submission_id(sub.id)
    assert (rec.status, rec.failure_code) == (status, code)
    if status == STATUS_API_FAILED:
        detail = await service(session).get_result(sub.id)
        assert detail.extraction_attempts == 9 and len(detail.extraction_failures) == 9 and detail.headline is None


async def test_an_identical_card_reuses_the_saved_result_but_keeps_its_own_identity(session):
    owner, me = await add_user(session), await add_user(session)
    orig, _ = await add_completed_submission(session, headline=HEADLINE, submitter_id=owner.id, published=CARD_DATE)
    await session.commit()
    _, mine = await accept(session, me.id)
    FakeOrchestrator.cache_hit_from = orig.id
    await service(session).process_submission(mine.id)
    row = await SubmissionRepository(session).get_by_id(mine.id)
    assert (row.submission_type, row.submitter_id, row.duplicate_of_submission_id, row.status) == (
        SubmissionType.PHOTO_CARD, me.id, orig.id, SubmissionStatus.EXPERT_REVIEW,
    )
    detail = await service(session).get_result(mine.id)
    assert detail.submission_id == mine.id and detail.image_url and detail.verification.cached
    assert detail.verification.claim_scope == ClaimScope.HEADLINE_ONLY


async def test_a_retry_after_extraction_never_reads_the_card_again(session):
    _, sub = await accept(session)
    FakeOrchestrator.crash = True
    with pytest.raises(RuntimeError):
        await service(session).process_submission(sub.id)
    FakeOrchestrator.crash = False
    await service(session).process_submission(sub.id)
    assert FakeExtractor.calls == 1
    assert (await SubmissionRepository(session).get_by_id(sub.id)).status == SubmissionStatus.EXPERT_REVIEW


async def test_a_card_without_a_recognised_outlet_is_checked_against_the_verified_sources(session):
    async def no_source(_repo):
        return extraction(None, source_reason="SOURCE_NOT_DETECTED",
                          details={"attempts": [], "source_reason": "SOURCE_NOT_DETECTED",
                                   "response": {"source_evidence": " Somoy TV "}})

    FakeExtractor.result = no_source
    _, sub = await accept(session)
    await service(session).process_submission(sub.id)
    ctx = FakeOrchestrator.captured["context"]
    assert (ctx.raw_claimed_source, ctx.source_resolution_reason) == ("", "SOURCE_NOT_DETECTED")
    row = await SubmissionRepository(session).get_by_id(sub.id)
    assert row.status == SubmissionStatus.EXPERT_REVIEW and row.claimed_source_id is None and row.claimed_source_text is None
    assert (await service(session).get_result(sub.id)).detected_source_text == "Somoy TV"


async def test_a_sourceless_card_resumes_after_a_crash_without_reading_it_again(session):
    _, sub = await accept(session)
    row = await SubmissionRepository(session).get_by_id(sub.id)
    row.headline = HEADLINE
    rec = await PhotocardExtractionRepository(session).get_by_submission_id(sub.id)
    rec.status, rec.extraction_details = STATUS_SUCCEEDED, {"source_reason": "SOURCE_UNRECOGNIZED"}
    await session.commit()
    await service(session).process_submission(sub.id)
    assert FakeExtractor.calls == 0
    assert FakeOrchestrator.captured["context"].source_resolution_reason == "SOURCE_UNRECOGNIZED"


async def test_jobs_that_cannot_succeed_fail_permanently_and_unreadable_storage_is_retried(session):
    text, _ = await add_completed_submission(session, headline="h", submitter_id=None)
    text.status = SubmissionStatus.PENDING
    await session.commit()
    with pytest.raises(PermanentJobError):  # not a photo card
        await service(session).process_submission(text.id)
    _, sub = await accept(session)
    with pytest.raises(RuntimeError):  # the image could not be read back: retryable
        await service(session, storage(image=None)).process_submission(sub.id)
    await session.delete(await PhotocardExtractionRepository(session).get_by_submission_id(sub.id))
    await session.commit()
    with pytest.raises(PermanentJobError):  # no stored image at all
        await service(session).process_submission(sub.id)
    assert await service(session).get_result(text.id) is None and await service(session).get_result(uuid.uuid4()) is None


def test_reading_failures_are_explained_in_plain_words():
    assert extraction_failures(None) == []
    assert extraction_failures({"skipped_reason": "Every Gemini API key has reached its limit"}) == [
        "Every image-reading key has reached its limit for now."
    ]
    assert extraction_failures({"skipped_reason": "Gemini API key is not configured", "attempts": [
        {"attempt": 1, "outcome": "quota_exhausted"}, {"attempt": 2, "outcome": "odd"}, {"attempt": 3, "outcome": "success"},
    ]}) == [
        "Image reading is not available on this server.",
        "Image reading attempt 1 the daily image-reading limit has been reached.",
        "Image reading attempt 2 failed.",
    ]
