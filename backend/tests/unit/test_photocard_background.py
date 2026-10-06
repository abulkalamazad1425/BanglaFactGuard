"""Photo-card background submission (image only), job durability, recovery
and lane isolation. Real SQLite DB; storage, Gemini extraction and the
pipeline's analysis stages are deterministic fakes."""

from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from sqlalchemy import func, select

from app.core.constants import (
    ClaimScope,
    SubmissionStatus,
    SubmissionType,
)
from app.core.exceptions import ImageStorageUnavailableError
from app.features.notifications.models import Notification
from app.features.photocard.claim_extraction import (
    API_FAILURE_MESSAGE,
    INVALID_CONTENT_MESSAGE,
    STATUS_API_FAILED,
    STATUS_INVALID_CONTENT,
    STATUS_SUCCEEDED,
    CardExtraction,
)
from app.features.photocard.service import PhotoCardService
from app.features.sources.models import VerifiedSource
from app.features.sources.repository import SourceRepository
from app.features.submissions.access import viewer_can_see
from app.features.submissions.models import Submission
from app.features.submissions.repository import (
    PhotocardExtractionRepository,
    RetrievedArticleRepository,
    SubmissionRepository,
)
from app.features.verification.job_repository import VerificationJobRepository
from app.features.verification.jobs import JobDeps, VerificationJobWorker, execute_job
from app.features.verification.models import VerificationResult
from app.features.verification.pipeline.stages.s13_result_persistence import ResultPersistenceStage
from app.features.verification.repository import ResultRepository
from app.shared.utils.hashing import compute_claim_hash
from db_helpers import add_completed_submission, add_source, add_user, make_session_factory
from pipeline_helpers import article, make_context, run_analysis

HEADLINE = "সরকার নতুন সেতু উদ্বোধন করেছে"
CARD_DATE = date(2026, 6, 7)


@pytest.fixture
async def db(tmp_path):
    engine, factory = await make_session_factory(str(tmp_path / "bg.db"))
    async with factory() as s:
        await add_source(s)
        await s.commit()
    yield factory
    await engine.dispose()


async def _source(db) -> VerifiedSource:
    async with db() as s:
        return (await s.execute(select(VerifiedSource))).scalar_one()


def _storage(upload_ok: bool = True) -> MagicMock:
    st = MagicMock()
    st.build_object_key = lambda sid, name: f"photocard/{sid}/{name}"
    st.upload = AsyncMock(return_value=upload_ok)
    st.download = AsyncMock(return_value=b"image-bytes")
    st.get_presigned_url = AsyncMock(return_value="https://minio/preview.png")
    return st


def _extraction(source=None, *, status=STATUS_SUCCEEDED, published=CARD_DATE, **kw) -> CardExtraction:
    ok = status == STATUS_SUCCEEDED
    base = dict(
        status=status,
        headline=HEADLINE if ok else None,
        source=source if ok else None,
        published_date=published if ok else None,
        attempts=1,
        model_version="gemini-test",
        details={"model": "gemini-test", "attempts": [{"attempt": 1, "batch": 1, "outcome": "success"}]},
        timings_ms={"gemini_extraction": 5},
    )
    base.update(kw)
    return CardExtraction(**base)


class FakeExtractor:
    """Stands in for PhotocardClaimExtractor; `result` may be a callable
    taking the source repo (so a test can return the DB's real source)."""

    result = None
    calls = 0

    def __init__(self, *, source_repo, http_client, **_):
        self.source_repo = source_repo

    async def extract(self, image_bytes):
        FakeExtractor.calls += 1
        r = FakeExtractor.result
        if callable(r):
            return await r(self.source_repo)
        return r


async def _ok(source_repo, published=CARD_DATE):
    [src] = await source_repo.list_active()
    return _extraction(src, published=published)


def _svc(session, *, storage=None) -> PhotoCardService:
    cache = MagicMock()
    cache.get_claim_result = AsyncMock(return_value=None)
    cache.set_claim_pointer = AsyncMock()
    cache.invalidate_claim = AsyncMock()
    return PhotoCardService(
        storage=storage or _storage(),
        submission_repo=SubmissionRepository(session),
        extraction_repo=PhotocardExtractionRepository(session),
        result_repo=ResultRepository(session),
        article_repo=RetrievedArticleRepository(session),
        source_repo=SourceRepository(session),
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
        stage = ResultPersistenceStage(
            self.repo, ResultRepository(session), RetrievedArticleRepository(session), MagicMock(set_claim_pointer=AsyncMock()), session=session
        )
        return await stage.execute(ctx)


@pytest.fixture(autouse=True)
def patch_pipeline(monkeypatch):
    FakeOrchestrator.captured = {}
    FakeOrchestrator.cache_hit_from = None
    FakeExtractor.result = _ok
    FakeExtractor.calls = 0
    monkeypatch.setattr("app.features.photocard.service.PipelineOrchestrator", FakeOrchestrator)
    monkeypatch.setattr(
        "app.features.photocard.service.build_photocard_stages", lambda **kw: []
    )
    monkeypatch.setattr("app.features.photocard.service.PhotocardClaimExtractor", FakeExtractor)


async def _accept(session, user_id=None):
    svc = _svc(session)
    sub = await svc.accept_upload(image_bytes=b"img", original_filename="card.png", submitter_id=user_id)
    return svc, sub


def _deps() -> JobDeps:
    return JobDeps(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(), photocard_storage=_storage())


# ── accept: image only, stored, owned, durable, nothing slow ─────────────


async def test_accept_stores_only_the_image_and_creates_an_owned_submission_and_job(db):
    async with db() as s:
        user = await add_user(s)
        await s.commit()
        svc, sub = await _accept(s, user.id)
        storage = svc.storage
    assert storage.upload.await_count == 1  # image bytes stored before acknowledging
    async with db() as s2:
        row = await SubmissionRepository(s2).get_by_id(sub.id)
        rec = await PhotocardExtractionRepository(s2).get_by_submission_id(sub.id)
        job = await VerificationJobRepository(s2).get_by_submission(sub.id)
        assert row.submission_type == SubmissionType.PHOTO_CARD and row.submitter_id == user.id
        assert row.status == SubmissionStatus.PENDING and row.processing_phase == "QUEUED"
        # nothing about the claim is known until Gemini has read the card
        assert row.headline is None and row.claimed_source_text is None and row.claimed_source_id is None
        assert row.published_date is None
        assert rec.image_object_key.endswith("card.png") and rec.status == "PENDING"
        assert job.kind == "PHOTO_CARD" and job.status == "QUEUED" and job.payload == {}


async def test_unstored_image_is_not_accepted(db):
    async with db() as s:
        svc = _svc(s, storage=_storage(upload_ok=False))
        with pytest.raises(ImageStorageUnavailableError):
            await svc.accept_upload(image_bytes=b"img", original_filename="c.png", submitter_id=None)
        assert (await s.execute(select(func.count()).select_from(Submission))).scalar_one() == 0


# ── HTTP 202 comes back before slow work; the job survives the client ────


async def test_upload_returns_202_before_slow_extraction_and_job_finishes_without_the_client(db, monkeypatch):
    from unittest.mock import patch

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
        )
        assert resp.status_code == 202, resp.text
        body = resp.json()
        assert body["status"] == "PENDING" and body["phase"] == "QUEUED"
        sid = uuid.UUID(body["submission_id"])

        # The response arrived while the (slow) job is still running: nothing
        # waited for Gemini/retrieval. The "client" now goes away - it never
        # polls again - and the job still completes server-side.
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


# ── end-to-end: extracted values become the claim ────────────────────────


async def test_job_turns_the_extracted_card_into_a_saved_headline_only_result(db):
    src = await _source(db)
    async with db() as s:
        user = await add_user(s)
        await s.commit()
        _, sub = await _accept(s, user.id)
    await execute_job(kind="PHOTO_CARD", submission_id=sub.id, payload={}, deps=_deps(), session_factory=db)

    ctx = FakeOrchestrator.captured["context"]
    # the verified source and printed date read from the card ARE the claim
    assert ctx.raw_claimed_source == "prothomalo.com" and ctx.published_date == CARD_DATE
    assert ctx.claim_scope == ClaimScope.HEADLINE_ONLY and ctx.raw_news_body is None
    async with db() as s:
        row = await SubmissionRepository(s).get_by_id(sub.id)
        rec = await PhotocardExtractionRepository(s).get_by_submission_id(sub.id)
        res = await ResultRepository(s).get_by_submission_id(sub.id)
        notes = (await s.execute(select(Notification).where(Notification.user_id == user.id))).scalars().all()
        detail = await _svc(s).get_result(sub.id)
    assert row.status == SubmissionStatus.EXPERT_REVIEW and row.headline == HEADLINE
    assert row.claimed_source_id == src.id and row.claimed_source_text == "prothomalo.com"
    assert row.published_date == CARD_DATE
    assert row.content_hash == compute_claim_hash(HEADLINE, "prothomalo.com", ClaimScope.HEADLINE_ONLY, published_date=CARD_DATE)
    assert rec.status == STATUS_SUCCEEDED and rec.attempts == 1 and rec.model_version == "gemini-test"
    assert res.claim_scope == "HEADLINE_ONLY" and res.body_comparison_status == "SKIPPED"
    assert res.headline_check_status == "COMPLETED"
    timings = res.analysis_details["timings"]
    assert set(timings["preprocessing_ms"]) == {"image_download", "gemini_extraction"}
    assert [n.link_url for n in notes] == [f"/verify/{sub.id}"]  # one notification, correct link
    assert detail.image_url and detail.headline == HEADLINE and detail.claim_scope == ClaimScope.HEADLINE_ONLY
    assert detail.claimed_source_text == "prothomalo.com" and detail.claimed_source_name == "প্রথম আলো"
    assert detail.published_date == CARD_DATE and detail.extraction_status == STATUS_SUCCEEDED
    assert detail.verification.overall_verdict is None and detail.verification.review_pending
    assert not hasattr(detail, "extracted_source_text") and not hasattr(detail, "ocr_raw_text")


async def test_card_without_a_printed_date_has_no_claimed_date(db):
    async def no_date(repo):
        return await _ok(repo, published=None)

    FakeExtractor.result = no_date
    async with db() as s:
        _, sub = await _accept(s)
    await execute_job(kind="PHOTO_CARD", submission_id=sub.id, payload={}, deps=_deps(), session_factory=db)
    assert FakeOrchestrator.captured["context"].published_date is None
    async with db() as s:
        row = await SubmissionRepository(s).get_by_id(sub.id)
    assert row.status == SubmissionStatus.EXPERT_REVIEW and row.published_date is None


# ── 7/8: API failure vs. card without headline/source: both stop, distinctly ─


@pytest.mark.parametrize("status, code, message", [
    (STATUS_API_FAILED, "gemini_unavailable", API_FAILURE_MESSAGE),
    (STATUS_INVALID_CONTENT, "source_not_identified", INVALID_CONTENT_MESSAGE),
])
async def test_failed_extraction_stops_before_verification_with_its_own_message(db, status, code, message):
    attempts = 9 if status == STATUS_API_FAILED else 1
    FakeExtractor.result = _extraction(
        status=status, failure_code=code, attempts=attempts,
        details={"attempts": [{"attempt": i, "batch": (i - 1) // 3 + 1, "outcome": "timeout"} for i in range(1, attempts + 1)]}
        if status == STATUS_API_FAILED else {"attempts": [{"attempt": 1, "outcome": "success"}]},
    )
    async with db() as s:
        user = await add_user(s)
        await s.commit()
        _, sub = await _accept(s, user.id)

    worker = VerificationJobWorker(_deps(), session_factory=db, stale_after_s=60, poll_interval_s=0.05)
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
        rec = await PhotocardExtractionRepository(s).get_by_submission_id(sub.id)
        job = await VerificationJobRepository(s).get_by_submission(sub.id)
        res = await ResultRepository(s).get_by_submission_id(sub.id)
        notes = (await s.execute(select(Notification).where(Notification.user_id == user.id))).scalars().all()
        detail = await _svc(s).get_result(sub.id)
    assert row.status == SubmissionStatus.FAILED and row.failure_reason == message
    assert FakeExtractor.calls == 1  # the job is not re-run: never more Gemini requests
    assert job.status == "FAILED" and job.attempts == 1
    assert "context" not in FakeOrchestrator.captured and res is None  # no verification ran
    assert rec.status == status and rec.failure_code == code
    assert [n.notification_type for n in notes] == ["VERIFICATION_FAILED"]
    assert detail.status == SubmissionStatus.FAILED and detail.failure_reason == message
    assert detail.headline is None and detail.claimed_source_text is None  # nothing fabricated
    if status == STATUS_API_FAILED:
        assert detail.extraction_attempts == 9 and len(detail.extraction_failures) == 9


# ── 3/19: an identical card reuses the saved result, keeping its identity ─


async def test_cached_reuse_preserves_photocard_identity_image_and_owner(db):
    async with db() as s:
        owner_of_original = await add_user(s)
        me = await add_user(s)
        orig, _ = await add_completed_submission(
            s, headline=HEADLINE, submitter_id=owner_of_original.id, published=CARD_DATE,
            submission_type=SubmissionType.SOURCE_BASED,
        )
        await s.commit()
        _, mine = await _accept(s, me.id)
    FakeOrchestrator.cache_hit_from = orig.id

    await execute_job(kind="PHOTO_CARD", submission_id=mine.id, payload={}, deps=_deps(), session_factory=db)

    async with db() as s:
        row = await SubmissionRepository(s).get_by_id(mine.id)
        rec = await PhotocardExtractionRepository(s).get_by_submission_id(mine.id)
        res = await ResultRepository(s).get_by_submission_id(mine.id)
        original = await SubmissionRepository(s).get_by_id(orig.id)
        detail = await _svc(s).get_result(mine.id)
    assert row.submission_type == SubmissionType.PHOTO_CARD  # not replaced by a text submission
    assert row.submitter_id == me.id and original.submitter_id == owner_of_original.id
    assert rec.image_object_key and rec.status == STATUS_SUCCEEDED
    assert row.duplicate_of_submission_id == orig.id and res.reused_from_submission_id == orig.id
    assert row.status == SubmissionStatus.EXPERT_REVIEW
    assert detail.submission_id == mine.id and detail.image_url and detail.verification.cached is True
    assert detail.verification.claim_scope == ClaimScope.HEADLINE_ONLY  # still headline-only


async def test_a_retry_after_extraction_never_calls_gemini_again(db):
    async with db() as s:
        _, sub = await _accept(s)

    class Boom(Exception):
        pass

    async def crash(_ctx):
        raise Boom("pipeline crashed")

    original_run = FakeOrchestrator.run
    FakeOrchestrator.run = staticmethod(crash)  # type: ignore[assignment]
    try:
        with pytest.raises(Boom):
            await execute_job(kind="PHOTO_CARD", submission_id=sub.id, payload={}, deps=_deps(), session_factory=db)
    finally:
        FakeOrchestrator.run = original_run  # type: ignore[assignment]
    await execute_job(kind="PHOTO_CARD", submission_id=sub.id, payload={}, deps=_deps(), session_factory=db)
    assert FakeExtractor.calls == 1
    async with db() as s:
        assert (await SubmissionRepository(s).get_by_id(sub.id)).status == SubmissionStatus.EXPERT_REVIEW


# ── 7: a slow photo card never blocks other requests ─────────────────────


async def test_photo_cards_waiting_on_gemini_never_block_text_jobs(db):
    async with db() as s:
        cards = []
        for _ in range(3):
            _, sub = await _accept(s)
            cards.append(sub.id)
    text = await _enqueue(db)  # queued AFTER the cards

    release = asyncio.Event()
    done: list[uuid.UUID] = []

    async def runner(**kw):
        if kw["kind"] == "PHOTO_CARD":
            await release.wait()  # e.g. waiting out Gemini batch pauses
        done.append(kw["submission_id"])

    worker = VerificationJobWorker(
        JobDeps(*(MagicMock() for _ in range(5))), session_factory=db,
        concurrency=1, photocard_concurrency=1, poll_interval_s=0.02, runner=runner,
    )
    worker.start()
    job = await _wait_job(db, text, "DONE")
    assert job.status == "DONE" and done == [text]  # text job ran while a card was still waiting
    release.set()
    for sid in cards:
        assert (await _wait_job(db, sid, "DONE")).status == "DONE"  # every card still processed
    await worker.stop()


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
    deps = _deps()
    await execute_job(kind="SOURCE_BASED", submission_id=sub.id, payload={}, deps=deps, session_factory=db)
    async with db() as s:
        assert (await s.execute(select(func.count()).select_from(VerificationResult))).scalar_one() == 1


# ── access: pending/failed cards are private to their owner ──────────────


async def test_pending_or_failed_submissions_are_visible_only_to_their_owner(db):
    async with db() as s:
        owner, other, staff = await add_user(s), await add_user(s), await add_user(s, role="expert")
        _, sub = await _accept(s, owner.id)
        anon_sub = Submission(
            submission_type=SubmissionType.PHOTO_CARD, content_hash="a", status=SubmissionStatus.PENDING
        )
    assert viewer_can_see(sub, owner) and viewer_can_see(sub, staff)
    assert not viewer_can_see(sub, other) and not viewer_can_see(sub, None)
    assert viewer_can_see(anon_sub, None)  # anonymous submissions keep id-only access
    sub.status = SubmissionStatus.EXPERT_REVIEW  # published results follow the public policy
    assert viewer_can_see(sub, None)
