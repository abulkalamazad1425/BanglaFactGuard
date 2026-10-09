"""Durable background execution of verification (text and photo-card).

What makes this durable (and what does not)
-------------------------------------------
* Accepting a submission writes a ``verification_jobs`` row in the SAME
  transaction as the submission. A job therefore cannot be lost between
  "accepted" and "scheduled".
* The worker claims jobs with ``FOR UPDATE SKIP LOCKED`` and keeps the claim
  alive with a heartbeat. A RUNNING job whose heartbeat has gone stale (the
  process crashed or restarted mid-run) is reclaimed on the next poll, so no
  accepted job is stranded. Recovery latency after a restart is therefore up
  to ``stale_after`` seconds.
* Execution depends on nothing from the originating request: the job reads
  the submission row (and, for photo cards, the stored image), opens its own
  DB session, and never needs the browser, polling or a request-scoped file.
* Retries are idempotent: a re-run that finds the submission already in
  expert review does nothing, and S12 / ``notify_once`` never duplicate a
  result or a notification.

This is a database-backed queue drained by an in-process worker, not a
separate broker: it survives restarts, but only while an application process
is running to drain it.
"""

from __future__ import annotations

import asyncio
import os
import socket
import uuid
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

import httpx
import structlog

from app.core.constants import JobPhase, SubmissionStatus
from app.core.exceptions import PermanentJobError, SourceNotFoundError
from app.db.engine import AsyncSessionLocal
from app.features.cache.cache_service import CacheService
from app.features.nlp.embedding_service import EmbeddingService
from app.features.nlp.ner_service import NERService
from app.features.nlp.nli_service import NLIService
from app.features.notifications.service import notify_once
from app.features.photocard.service import PhotoCardService
from app.features.photocard.storage_service import PhotoCardStorageService
from app.features.sources.repository import SourceRepository
from app.features.submissions.repository import (
    PhotocardExtractionRepository,
    RetrievedArticleRepository,
    SubmissionRepository,
)
from app.features.verification.job_repository import VerificationJobRepository
from app.features.verification.repository import ResultRepository
from app.features.verification.service import VerificationService

logger = structlog.get_logger(__name__)


@dataclass
class JobDeps:
    """Process-wide services the job needs (taken from ``app.state``)."""

    cache_service: CacheService
    embedding_service: EmbeddingService
    ner_service: NERService
    nli_service: NLIService
    http_client: httpx.AsyncClient
    photocard_storage: PhotoCardStorageService | None = None
    multimodal_loader: Any = None
    multimodal_storage: Any = None

    @classmethod
    def from_app_state(cls, state: Any) -> "JobDeps":
        return cls(
            cache_service=state.cache_service,
            embedding_service=state.embedding_service,
            ner_service=state.ner_service,
            nli_service=state.nli_service,
            http_client=state.http_client,
            photocard_storage=getattr(state, "photocard_storage", None),
            multimodal_loader=getattr(state, "multimodal_loader", None),
            multimodal_storage=getattr(state, "multimodal_storage", None),
        )


async def execute_job(
    *,
    kind: str,
    submission_id: uuid.UUID,
    payload: dict,
    deps: JobDeps,
    session_factory: Callable[[], Any] = AsyncSessionLocal,
) -> None:
    """Run one job body in its own session and commit on success."""
    async with session_factory() as session:
        submission_repo = SubmissionRepository(session)
        submission = await submission_repo.get_by_id_or_none(submission_id)
        if submission is None:
            raise PermanentJobError("The submission no longer exists.")
        if submission.status in (
            SubmissionStatus.EXPERT_REVIEW,
            SubmissionStatus.FINALIZED,
            SubmissionStatus.ESCALATED,
        ):
            return  # idempotent: already processed

        ctx = _JobContext(
            session=session,
            submission_id=submission_id,
            submission=submission,
            payload=payload,
            deps=deps,
            submission_repo=submission_repo,
            result_repo=ResultRepository(session),
            article_repo=RetrievedArticleRepository(session),
            source_repo=SourceRepository(session),
        )
        handler = _HANDLERS.get(kind, _run_source_based)
        try:
            await handler(ctx)
            await session.commit()
        except SourceNotFoundError as exc:
            await session.rollback()
            raise PermanentJobError(
                f"The claimed source could not be resolved: {exc.claimed_source!r}"
            ) from exc
        except Exception:
            await session.rollback()
            raise


@dataclass
class _JobContext:
    """What one job handler works with: the job's own session, the loaded
    submission and the repositories bound to that session."""

    session: Any
    submission_id: uuid.UUID
    submission: Any
    payload: dict
    deps: JobDeps
    submission_repo: SubmissionRepository
    result_repo: ResultRepository
    article_repo: RetrievedArticleRepository
    source_repo: SourceRepository


async def _mark_verifying(ctx: _JobContext) -> None:
    """Visible PROCESSING/VERIFYING before the slow part starts."""
    await ctx.submission_repo.mark_processing(ctx.submission_id)
    await ctx.submission_repo.set_phase(ctx.submission_id, JobPhase.VERIFYING.value)
    await ctx.session.commit()


async def _run_multimodal(ctx: _JobContext) -> None:
    from app.features.multimodal.service import MultimodalPredictionService
    deps = ctx.deps
    if deps.multimodal_loader is None or not deps.multimodal_loader.is_loaded:
        raise PermanentJobError("The multimodal model is unavailable. Please try again later.")
    if deps.multimodal_storage is None:
        raise PermanentJobError("Image storage is unavailable.")
    await _mark_verifying(ctx)
    await MultimodalPredictionService(
        db=ctx.session, loader=deps.multimodal_loader, storage=deps.multimodal_storage,
    ).process_queued(ctx.submission, ctx.payload)


async def _run_photocard(ctx: _JobContext) -> None:
    deps = ctx.deps
    service = PhotoCardService(
        storage=deps.photocard_storage or PhotoCardStorageService(),
        submission_repo=ctx.submission_repo,
        extraction_repo=PhotocardExtractionRepository(ctx.session),
        result_repo=ctx.result_repo,
        article_repo=ctx.article_repo,
        source_repo=ctx.source_repo,
        cache_service=deps.cache_service,
        embedding_service=deps.embedding_service,
        ner_service=deps.ner_service,
        nli_service=deps.nli_service,
        http_client=deps.http_client,
    )
    # Photo cards set their own phases (extraction comes before verification).
    await service.process_submission(ctx.submission_id)


async def _run_source_based(ctx: _JobContext) -> None:
    deps = ctx.deps
    service = VerificationService(
        submission_repo=ctx.submission_repo,
        result_repo=ctx.result_repo,
        article_repo=ctx.article_repo,
        source_repo=ctx.source_repo,
        cache_service=deps.cache_service,
        embedding_service=deps.embedding_service,
        ner_service=deps.ner_service,
        nli_service=deps.nli_service,
        http_client=deps.http_client,
    )
    await _mark_verifying(ctx)
    await service.run_for_submission(ctx.submission_id)


# Job kind -> handler. Any other kind (SOURCE_BASED) runs the text pipeline.
_HANDLERS: dict[str, Callable[[_JobContext], Awaitable[None]]] = {
    "MULTIMODAL": _run_multimodal,
    "PHOTO_CARD": _run_photocard,
}


PHOTO_CARD_KINDS = ("PHOTO_CARD",)


@dataclass
class _Lane:
    """One independently bounded queue consumer. Photo cards get their own
    lane: their Gemini step can wait out retries for minutes, and must never
    hold the slots that text and text & image jobs need (nor vice versa)."""

    name: str
    concurrency: int
    kinds: tuple[str, ...] | None = None          # only these kinds
    exclude_kinds: tuple[str, ...] | None = None  # every kind but these
    slots: asyncio.Semaphore | None = None
    wake: asyncio.Event | None = None
    task: asyncio.Task | None = None


class VerificationJobWorker:
    """Drains ``verification_jobs`` with bounded concurrency, in two lanes:
    photo cards, and everything else."""

    def __init__(
        self,
        deps: JobDeps,
        *,
        session_factory: Callable[[], Any] = AsyncSessionLocal,
        concurrency: int = 2,
        photocard_concurrency: int = 4,
        poll_interval_s: float = 5.0,
        stale_after_s: float = 120.0,
        heartbeat_interval_s: float = 30.0,
        runner: Callable[..., Any] | None = None,
    ) -> None:
        self.deps = deps
        self._session_factory = session_factory
        self._poll = poll_interval_s
        self._stale_after = stale_after_s
        self._heartbeat_every = heartbeat_interval_s
        self._runner = runner or execute_job
        self._worker_id = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:6]}"
        self._stop = False
        self._inflight: set[asyncio.Task] = set()
        self._lanes = [
            _Lane("general", max(1, concurrency), exclude_kinds=PHOTO_CARD_KINDS),
            _Lane("photocard", max(1, photocard_concurrency), kinds=PHOTO_CARD_KINDS),
        ]

    # ── lifecycle ────────────────────────────────────────────────────────

    def start(self) -> None:
        if any(lane.task for lane in self._lanes):
            return
        self._stop = False
        for lane in self._lanes:
            lane.slots = asyncio.Semaphore(lane.concurrency)
            lane.wake = asyncio.Event()
            lane.task = asyncio.create_task(self._run_loop(lane), name=f"verification-job-worker-{lane.name}")
        logger.info("job_worker_started", worker_id=self._worker_id,
                    lanes={lane.name: lane.concurrency for lane in self._lanes})

    async def stop(self) -> None:
        self._stop = True
        self.wake()
        tasks = [lane.task for lane in self._lanes if lane.task]
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for t in list(self._inflight):
            t.cancel()
        await asyncio.gather(*self._inflight, return_exceptions=True)
        for lane in self._lanes:
            lane.task = None

    def wake(self) -> None:
        """Poke the worker after enqueueing; purely a latency optimisation."""
        for lane in self._lanes:
            if lane.wake is not None:
                lane.wake.set()

    # ── loop ─────────────────────────────────────────────────────────────

    async def _run_loop(self, lane: _Lane) -> None:
        assert lane.slots is not None and lane.wake is not None
        while not self._stop:
            try:
                await lane.slots.acquire()
                job = await self._claim(lane)
                if job is None:
                    lane.slots.release()
                    lane.wake.clear()
                    try:
                        await asyncio.wait_for(lane.wake.wait(), timeout=self._poll)
                    except asyncio.TimeoutError:
                        pass
                    continue
                task = asyncio.create_task(self._run_job(job, lane))
                self._inflight.add(task)
                task.add_done_callback(self._inflight.discard)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - the loop must survive anything
                lane.slots.release()
                logger.error("job_worker_loop_error", lane=lane.name, error=str(exc)[:200])
                await asyncio.sleep(self._poll)

    async def _claim(self, lane: _Lane) -> dict | None:
        async with self._session_factory() as session:
            repo = VerificationJobRepository(session)
            job = await repo.claim_next(
                self._worker_id, stale_after_s=self._stale_after,
                kinds=lane.kinds, exclude_kinds=lane.exclude_kinds,
            )
            if job is None:
                await session.rollback()
                return None
            info = {
                "id": job.id,
                "kind": job.kind,
                "submission_id": job.submission_id,
                "payload": dict(job.payload or {}),
                "attempts": job.attempts,
            }
            await session.commit()
            return info

    async def _run_job(self, job: dict, lane: _Lane) -> None:
        assert lane.slots is not None
        log = logger.bind(job_id=str(job["id"]), submission_id=str(job["submission_id"]), kind=job["kind"])
        heartbeat = asyncio.create_task(self._heartbeat(job["id"]))
        try:
            log.info("verification_job_started", attempt=job["attempts"], lane=lane.name)
            await self._runner(
                kind=job["kind"],
                submission_id=job["submission_id"],
                payload=job["payload"],
                deps=self.deps,
                session_factory=self._session_factory,
            )
            async with self._session_factory() as session:
                await VerificationJobRepository(session).mark_done(job["id"])
                await session.commit()
            log.info("verification_job_completed")
        except asyncio.CancelledError:
            raise
        except PermanentJobError as exc:
            await self._fail(job, exc.reason, permanent=True)
        except Exception as exc:  # noqa: BLE001
            log.error("verification_job_failed", error=str(exc)[:200])
            await self._fail(job, "Verification could not be completed. Please try again.", permanent=False, error=str(exc))
        finally:
            heartbeat.cancel()
            lane.slots.release()

    async def _heartbeat(self, job_id: uuid.UUID) -> None:
        try:
            while True:
                await asyncio.sleep(self._heartbeat_every)
                async with self._session_factory() as session:
                    await VerificationJobRepository(session).heartbeat(job_id)
                    await session.commit()
        except asyncio.CancelledError:
            pass
        except Exception as exc:  # noqa: BLE001
            logger.warning("job_heartbeat_failed", error=str(exc)[:120])

    async def _fail(self, job: dict, reason: str, *, permanent: bool, error: str | None = None) -> None:
        """Retry or terminally fail. A terminal failure marks the submission
        FAILED (with a user-presentable reason) and notifies the owner exactly
        once. Notification trouble never changes the failure itself."""
        try:
            async with self._session_factory() as session:
                repo = VerificationJobRepository(session)
                terminal = await repo.release_or_fail(
                    job["id"], error or reason, permanent=permanent
                )
                if terminal:
                    sub_repo = SubmissionRepository(session)
                    transitioned = await sub_repo.mark_failed(job["submission_id"], reason)
                    submission = await sub_repo.get_by_id_or_none(job["submission_id"])
                    if transitioned and submission and submission.submitter_id:
                        await notify_once(
                            session,
                            user_id=submission.submitter_id,
                            notification_type="VERIFICATION_FAILED",
                            link_url=f"/verify/{submission.id}",
                            title="Verification could not be completed",
                            body=reason,
                        )
                else:
                    await SubmissionRepository(session).set_phase(job["submission_id"], JobPhase.QUEUED.value)
                await session.commit()
        except Exception as exc:  # noqa: BLE001
            logger.error("job_fail_handling_error", error=str(exc)[:200])
            # The row stays RUNNING with a stale heartbeat and will be reclaimed.
