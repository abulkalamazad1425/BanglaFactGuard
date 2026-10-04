"""Photo-card background submission, job durability and recovery
(acceptance 19-29, 22). Real SQLite DB; OCR, storage, Gemini and the
pipeline's analysis stages are deterministic fakes."""

from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from sqlalchemy import func, select, update

from app.core.constants import (
    ClaimScope,
    SourceStatus,
    SubmissionStatus,
    SubmissionType,
)
from app.core.exceptions import ImageStorageUnavailableError, PermanentJobError
from app.features.notifications.models import Notification
from app.features.photocard.gemini_extractor import HeadlineExtraction
from app.features.photocard.ocr_service import OcrLine, OcrOutput
from app.features.photocard.service import PhotoCardService
from app.features.sources.repository import SourceRepository
from app.features.submissions.access import viewer_can_see
from app.features.submissions.models import OcrExtraction, Submission
from app.features.submissions.repository import (
    OcrExtractionRepository,
    RetrievedArticleRepository,
    SubmissionRepository,
)
from app.features.verification.job_repository import VerificationJobRepository
from app.features.verification.jobs import JobDeps, VerificationJobWorker, execute_job
from app.features.verification.models import VerificationJob, VerificationResult
from app.features.verification.pipeline.stages.s12_persistence import PersistenceStage
from app.features.verification.repository import ResultRepository
from app.shared.utils.hashing import compute_claim_hash
from db_helpers import add_completed_submission, add_source, add_user, make_session_factory
from pipeline_helpers import article, make_context, run_analysis

HEADLINE = "সরকার নতুন সেতু উদ্বোধন করেছে"
CLAIMED_DATE = date(2026, 6, 7)


@pytest.fixture
async def db(tmp_path):
    engine, factory = await make_session_factory(str(tmp_path / "bg.db"))
    async with factory() as s:
        await add_source(s)
        await s.commit()
    yield factory
    await engine.dispose()


def _storage(upload_ok: bool = True) -> MagicMock:
    st = MagicMock()
    st.build_object_key = lambda sid, name: f"photocard/{sid}/{name}"
    st.upload = AsyncMock(return_value=upload_ok)
    st.download = AsyncMock(return_value=b"image-bytes")
    st.get_presigned_url = AsyncMock(return_value="https://minio/preview.png")
    return st


def _ocr() -> MagicMock:
    ocr = MagicMock()
    ocr.recognize = AsyncMock(
        return_value=OcrOutput(
            text=HEADLINE,
            lines=[OcrLine(text=HEADLINE, confidence=0.9)],
            confidence=0.9,
            engine="tesseract",
            variant="raw",
        )
    )
    return ocr


def _extraction(headline: str = HEADLINE, **kw) -> HeadlineExtraction:
    base = dict(
        headline=headline,
        detected_source_text=None,
        detected_date_text=None,
        warnings=[],
        extractor_used="EXISTING_FALLBACK",
        model_version=None,
    )
    base.update(kw)
    return HeadlineExtraction(**base)


def _svc(session, *, storage=None, ocr=None) -> PhotoCardService:
    cache = MagicMock()
    cache.get_claim_result = AsyncMock(return_value=None)
    cache.set_claim_pointer = AsyncMock()
    cache.invalidate_claim = AsyncMock()
    return PhotoCardService(
        ocr_service=ocr or _ocr(),
        storage=storage or _storage(),
        submission_repo=SubmissionRepository(session),
        ocr_repo=OcrExtractionRepository(session),
        result_repo=ResultRepository(session),
        article_repo=RetrievedArticleRepository(session),
        # SQLite cannot evaluate the JSONB alias-containment lookup; the
        # static alias table resolves the claimed source in these tests.
        source_repo=MagicMock(resolve_source=AsyncMock(return_value=None)),
        cache_service=cache,
        embedding_service=MagicMock(),
        ner_service=MagicMock(),
        nli_service=MagicMock(),
        http_client=MagicMock(),
    )


class FakeOrchestrator:
    """Stands in for the 12-stage orchestrator: runs the real analysis
    (S08-S11, deterministic fakes) and the REAL persistence stage."""

    captured: dict = {}
    cache_hit_from: uuid.UUID | None = None

    def __init__(self, *, stages=None, submission_repo=None):
        self.repo = submission_repo

    async def run(self, context):
        FakeOrchestrator.captured["context"] = context
        if FakeOrchestrator.cache_hit_from:
            context.cache_hit = True
            context.reused_from_submission_id = FakeOrchestrator.cache_hit_from
            return context
        ctx = make_context(
            context.raw_headline,
            scope=context.claim_scope,
            published_date=context.published_date,
            top=article(context.raw_headline, context.raw_headline + "।", published=context.published_date),
        )
        ctx.submission_id = context.submission_id
        ctx.submitter_id = context.submitter_id
        ctx.content_hash = compute_claim_hash(
            context.raw_headline, "prothomalo.com", context.claim_scope, published_date=context.published_date
        )
        ctx = await run_analysis(ctx)
        session = self.repo.session
        stage = PersistenceStage(
            self.repo, ResultRepository(session), RetrievedArticleRepository(session), MagicMock(set_claim_pointer=AsyncMock()), session=session
        )
        return await stage.execute(ctx)


@pytest.fixture(autouse=True)
def patch_pipeline(monkeypatch):
    FakeOrchestrator.captured = {}
    FakeOrchestrator.cache_hit_from = None
    monkeypatch.setattr("app.features.photocard.service.PipelineOrchestrator", FakeOrchestrator)
    monkeypatch.setattr(
        "app.features.photocard.service.build_photocard_stages", lambda **kw: []
    )
    monkeypatch.setattr(
        "app.features.photocard.service.extract_headline", AsyncMock(return_value=_extraction())
    )
    monkeypatch.setattr(
        "app.features.photocard.service.SourceDetector",
        lambda repo: MagicMock(detect=AsyncMock(return_value=[])),
    )


async def _accept(session, user_id=None, **kw):
    svc = _svc(session)
    sub = await svc.accept_upload(
        image_bytes=b"img",
        original_filename="card.png",
        claimed_source_text=kw.pop("claimed", "প্রথম আলো"),
        published_date=kw.pop("published", CLAIMED_DATE),
        submitter_id=user_id,
        **kw,
    )
    return svc, sub


# ── accept: stored, owned, durable, nothing slow ─────────────────────────


async def test_accept_stores_image_creates_owned_photocard_submission_and_job(db):
    async with db() as s:
        user = await add_user(s)
        await s.commit()
        svc, sub = await _accept(s, user.id)
        storage = svc.storage
    assert storage.upload.await_count == 1  # image bytes stored before acknowledging
    async with db() as s2:
        row = await SubmissionRepository(s2).get_by_id(sub.id)
        ocr = await OcrExtractionRepository(s2).get_by_submission_id(sub.id)
        job = await VerificationJobRepository(s2).get_by_submission(sub.id)
        assert row.submission_type == SubmissionType.PHOTO_CARD and row.submitter_id == user.id
        assert row.status == SubmissionStatus.PENDING and row.processing_phase == "QUEUED"
        assert row.headline is None  # not known until extraction; the row still exists
        assert ocr.image_object_key.endswith("card.png")
        assert job.kind == "PHOTO_CARD" and job.status == "QUEUED"


async def test_unstored_image_is_not_accepted(db):
    async with db() as s:
        svc = _svc(s, storage=_storage(upload_ok=False))
        with pytest.raises(ImageStorageUnavailableError):
            await svc.accept_upload(
                image_bytes=b"img", original_filename="c.png", claimed_source_text="প্রথম আলো",
                published_date=None, submitter_id=None,
            )
        assert (await s.execute(select(func.count()).select_from(Submission))).scalar_one() == 0


# ── 23/24: HTTP 202 comes back before slow work; the job survives the client ─


async def test_upload_returns_202_before_slow_extraction_and_job_finishes_without_the_client(db, monkeypatch):
    from unittest.mock import patch

    from fastapi import FastAPI

    from app.features.auth.security import get_current_user_optional
    from app.features.photocard.dependencies import get_photocard_service

    with patch("app.main.lifespan"):
        from app.main import create_app

        app = create_app()

    release = asyncio.Event()
    finished = asyncio.Event()
    started = asyncio.Event()

    async def slow_runner(**kw):
        started.set()
        await release.wait()  # "deliberately slow extraction"
        finished.set()

    worker = VerificationJobWorker(
        JobDeps(*(MagicMock() for _ in range(5))),
        session_factory=db,
        poll_interval_s=0.05,
        runner=slow_runner,
    )
    worker.start()
    app.state.job_worker = worker

    async with db() as setup:
        user = await add_user(setup)
        await setup.commit()

    async def provide_service():
        async with db() as s:
            yield _svc(s)

    class U:  # minimal authenticated user
        id = user.id
        role = "user"

    app.dependency_overrides[get_photocard_service] = provide_service
    app.dependency_overrides[get_current_user_optional] = lambda: U()

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as client:
        resp = await client.post(
            "/api/v1/photocard/verify/async",
            files={"image": ("card.png", b"\x89PNG\r\n\x1a\n" + b"0" * 64, "image/png")},
            data={"claimed_source_text": "প্রথম আলো", "published_date": "2026-06-07"},
        )
        assert resp.status_code == 202, resp.text
        body = resp.json()
        assert body["status"] == "PENDING" and body["phase"] == "QUEUED"
        sid = uuid.UUID(body["submission_id"])

        # The response arrived while the (slow) job is still running: nothing
        # waited for OCR/Gemini/retrieval. The "client" now goes away - it
        # never polls again - and the job still completes server-side.
        await asyncio.wait_for(started.wait(), 2)
        assert not finished.is_set()
        release.set()
        await asyncio.wait_for(finished.wait(), 2)

        for _ in range(50):
            async with db() as s:
                job = await VerificationJobRepository(s).get_by_submission(sid)
                if job.status == "DONE":
                    break
            await asyncio.sleep(0.02)
        assert job.status == "DONE"
    await worker.stop()


# ── end-to-end: process → saved result → My Submissions / detail ─────────


async def test_job_processes_card_into_a_saved_headline_only_result(db):
    async with db() as s:
        user = await add_user(s)
        await s.commit()
        _, sub = await _accept(s, user.id)
    deps = JobDeps(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(), ocr_service=_ocr(), photocard_storage=_storage())
    await execute_job(kind="PHOTO_CARD", submission_id=sub.id, payload={}, deps=deps, session_factory=db)

    async with db() as s:
        row = await SubmissionRepository(s).get_by_id(sub.id)
        res = await ResultRepository(s).get_by_submission_id(sub.id)
        notes = (await s.execute(select(Notification).where(Notification.user_id == user.id))).scalars().all()
        detail = await _svc(s).get_result(sub.id)
    assert row.status == SubmissionStatus.EXPERT_REVIEW and row.headline == HEADLINE
    assert row.content_hash == compute_claim_hash(HEADLINE, "prothomalo.com", ClaimScope.HEADLINE_ONLY, published_date=CLAIMED_DATE)
    assert res.claim_scope == "HEADLINE_ONLY" and res.body_similarity is None and res.ai_consensus_label is None
    assert [n.link_url for n in notes] == [f"/verify/{sub.id}"]  # one notification, correct link
    # the detail page works: image, extracted headline, headline-only scope, no overall verdict
    assert detail.image_url and detail.headline == HEADLINE and detail.claim_scope == ClaimScope.HEADLINE_ONLY
    assert detail.verification.overall_verdict is None and detail.verification.review_pending
    assert detail.verification.scores.body_similarity is None


# ── 22: user source/date are authoritative ───────────────────────────────


async def test_image_detected_source_and_date_never_overwrite_user_values(db, monkeypatch):
    monkeypatch.setattr(
        "app.features.photocard.service.extract_headline",
        AsyncMock(return_value=_extraction(detected_source_text="যুগান্তর", detected_date_text="১ জানুয়ারি ২০২০")),
    )
    async with db() as s:
        _, sub = await _accept(s, None, claimed="প্রথম আলো", published=CLAIMED_DATE)
    deps = JobDeps(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(), ocr_service=_ocr(), photocard_storage=_storage())
    await execute_job(kind="PHOTO_CARD", submission_id=sub.id, payload={}, deps=deps, session_factory=db)

    ctx = FakeOrchestrator.captured["context"]
    assert ctx.raw_claimed_source == "প্রথম আলো" and ctx.published_date == CLAIMED_DATE
    assert ctx.claim_scope == ClaimScope.HEADLINE_ONLY and ctx.raw_news_body is None
    async with db() as s:
        row = await SubmissionRepository(s).get_by_id(sub.id)
        ocr = await OcrExtractionRepository(s).get_by_submission_id(sub.id)
    assert row.claimed_source_text == "প্রথম আলো" and row.published_date == CLAIMED_DATE
    assert ocr.detected_source_text == "যুগান্তর" and ocr.detected_date_text == "১ জানুয়ারি ২০২০"  # kept as metadata
    assert any("does not match" in w or "does not clearly match" in w for w in ocr.extraction_warnings)


# ── 21/27: extraction failure is terminal, explained, notified once ──────


async def test_unusable_extraction_fails_the_job_with_a_reason_and_no_automated_result(db, monkeypatch):
    monkeypatch.setattr(
        "app.features.photocard.service.extract_headline",
        AsyncMock(return_value=_extraction(headline="", warnings=["No Bangla claim text survived cleaning."])),
    )
    async with db() as s:
        user = await add_user(s)
        await s.commit()
        _, sub = await _accept(s, user.id)

    deps = JobDeps(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(), ocr_service=_ocr(), photocard_storage=_storage())
    worker = VerificationJobWorker(deps, session_factory=db, stale_after_s=60, poll_interval_s=0.05)
    worker.start()
    for _ in range(100):
        async with db() as s:
            row = await SubmissionRepository(s).get_by_id(sub.id)
        if row.status == SubmissionStatus.FAILED:
            break
        await asyncio.sleep(0.02)
    await worker.stop()

    async with db() as s:
        row = await SubmissionRepository(s).get_by_id(sub.id)
        job = await VerificationJobRepository(s).get_by_submission(sub.id)
        res = await ResultRepository(s).get_by_submission_id(sub.id)
        notes = (await s.execute(select(Notification).where(Notification.user_id == user.id))).scalars().all()
        detail = await _svc(s).get_result(sub.id)
    assert row.status == SubmissionStatus.FAILED and "headline" in row.failure_reason.lower()
    assert job.status == "FAILED" and job.attempts == 1  # permanent: not retried
    assert res is None  # never Source Not Found / Content Altered: no check ran
    assert [n.notification_type for n in notes] == ["VERIFICATION_FAILED"]
    assert detail.status == SubmissionStatus.FAILED and detail.failure_reason == row.failure_reason
    assert detail.verification is None
    # ocr text is still kept for the owner / experts
    assert detail.headline is None


# ── 19: cache reuse keeps the photo card's identity ──────────────────────


async def test_cached_reuse_preserves_photocard_identity_image_and_owner(db):
    async with db() as s:
        owner_of_original = await add_user(s)
        me = await add_user(s)
        orig, _ = await add_completed_submission(
            s, headline=HEADLINE, submitter_id=owner_of_original.id, published=CLAIMED_DATE,
            submission_type=SubmissionType.SOURCE_BASED,
        )
        await s.commit()
        _, mine = await _accept(s, me.id)
    FakeOrchestrator.cache_hit_from = orig.id

    deps = JobDeps(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(), ocr_service=_ocr(), photocard_storage=_storage())
    await execute_job(kind="PHOTO_CARD", submission_id=mine.id, payload={}, deps=deps, session_factory=db)

    async with db() as s:
        row = await SubmissionRepository(s).get_by_id(mine.id)
        ocr = await OcrExtractionRepository(s).get_by_submission_id(mine.id)
        res = await ResultRepository(s).get_by_submission_id(mine.id)
        original = await SubmissionRepository(s).get_by_id(orig.id)
        detail = await _svc(s).get_result(mine.id)
    assert row.submission_type == SubmissionType.PHOTO_CARD  # not replaced by a text submission
    assert row.submitter_id == me.id and original.submitter_id == owner_of_original.id
    assert ocr.image_object_key and ocr.raw_extracted_text == HEADLINE
    assert row.duplicate_of_submission_id == orig.id and res.reused_from_submission_id == orig.id
    assert row.status == SubmissionStatus.EXPERT_REVIEW
    assert detail.submission_id == mine.id and detail.image_url and detail.verification.cached is True
    assert detail.verification.scores.body_similarity is None  # still headline-only


async def test_force_refresh_reaches_the_pipeline(db):
    async with db() as s:
        _, sub = await _accept(s, None, force_refresh=True)
    async with db() as s:
        job = await VerificationJobRepository(s).get_by_submission(sub.id)
    assert job.payload == {"force_refresh": True}
    deps = JobDeps(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(), ocr_service=_ocr(), photocard_storage=_storage())
    await execute_job(kind="PHOTO_CARD", submission_id=sub.id, payload=job.payload, deps=deps, session_factory=db)
    assert FakeOrchestrator.captured["context"].force_refresh is True


# ── 28/29: restart recovery, retries, no duplicates ──────────────────────


async def _enqueue(db, status="QUEUED", locked_ago: float | None = None):
    async with db() as s:
        sub = Submission(
            submission_type=SubmissionType.SOURCE_BASED, headline=HEADLINE, claimed_source_text="প্রথম আলো",
            content_hash=uuid.uuid4().hex, status=SubmissionStatus.PENDING,
        )
        s.add(sub)
        await s.flush()
        job = await VerificationJobRepository(s).enqueue(sub.id, "SOURCE_BASED")
        job.status = status
        if locked_ago is not None:
            job.locked_at = datetime.now(timezone.utc) - timedelta(seconds=locked_ago)
        await s.commit()
        return sub.id


async def _wait_job(db, sid, status, tries=100):
    for _ in range(tries):
        async with db() as s:
            job = await VerificationJobRepository(s).get_by_submission(sid)
        if job.status == status:
            return job
        await asyncio.sleep(0.02)
    return job


async def test_queued_and_crash_stranded_jobs_are_recovered_by_a_fresh_worker(db):
    queued = await _enqueue(db)  # accepted, process died before running it
    stranded = await _enqueue(db, status="RUNNING", locked_ago=600)  # crashed mid-run
    alive = await _enqueue(db, status="RUNNING", locked_ago=1)  # still heartbeating elsewhere

    ran: list[uuid.UUID] = []

    async def runner(**kw):
        ran.append(kw["submission_id"])

    worker = VerificationJobWorker(  # a "restarted" process: brand-new worker instance
        JobDeps(*(MagicMock() for _ in range(5))), session_factory=db,
        stale_after_s=120, poll_interval_s=0.05, runner=runner,
    )
    worker.start()
    await _wait_job(db, queued, "DONE")
    await _wait_job(db, stranded, "DONE")
    await worker.stop()
    assert set(ran) == {queued, stranded}
    async with db() as s:
        assert (await VerificationJobRepository(s).get_by_submission(alive)).status == "RUNNING"


async def test_retry_then_terminal_failure_notifies_the_owner_exactly_once(db):
    async with db() as s:
        user = await add_user(s)
        sub = Submission(
            submission_type=SubmissionType.SOURCE_BASED, headline=HEADLINE, claimed_source_text="প্রথম আলো",
            content_hash="h", status=SubmissionStatus.PENDING, submitter_id=user.id,
        )
        s.add(sub)
        await s.flush()
        await VerificationJobRepository(s).enqueue(sub.id, "SOURCE_BASED")
        await s.commit()
    attempts = []

    async def failing(**kw):
        attempts.append(1)
        raise RuntimeError("boom")

    worker = VerificationJobWorker(
        JobDeps(*(MagicMock() for _ in range(5))), session_factory=db, poll_interval_s=0.02, runner=failing
    )
    worker.start()
    job = await _wait_job(db, sub.id, "FAILED", tries=300)
    await worker.stop()
    assert len(attempts) == job.attempts == 3  # bounded retries
    async with db() as s:
        row = await SubmissionRepository(s).get_by_id(sub.id)
        notes = (await s.execute(select(Notification).where(Notification.user_id == user.id))).scalars().all()
    assert row.status == SubmissionStatus.FAILED and row.failure_reason
    assert [n.notification_type for n in notes] == ["VERIFICATION_FAILED"]


async def test_rerunning_a_finished_job_is_a_no_op(db):
    async with db() as s:
        sub, _ = await add_completed_submission(s, headline=HEADLINE, submitter_id=None)
        await s.commit()
    runner = AsyncMock()
    deps = JobDeps(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(), ocr_service=_ocr(), photocard_storage=_storage())
    await execute_job(kind="SOURCE_BASED", submission_id=sub.id, payload={}, deps=deps, session_factory=db)
    async with db() as s:
        assert (await s.execute(select(func.count()).select_from(VerificationResult))).scalar_one() == 1


# ── access: pending/failed cards are private to their owner ──────────────


async def test_pending_or_failed_submissions_are_visible_only_to_their_owner(db):
    async with db() as s:
        owner, other, staff = await add_user(s), await add_user(s), await add_user(s, role="expert")
        _, sub = await _accept(s, owner.id)
        anon_sub = Submission(
            submission_type=SubmissionType.PHOTO_CARD, claimed_source_text="x", content_hash="a", status=SubmissionStatus.PENDING
        )
    assert viewer_can_see(sub, owner) and viewer_can_see(sub, staff)
    assert not viewer_can_see(sub, other) and not viewer_can_see(sub, None)
    assert viewer_can_see(anon_sub, None)  # anonymous submissions keep id-only access
    sub.status = SubmissionStatus.EXPERT_REVIEW  # published results follow the public policy
    assert viewer_can_see(sub, None)
