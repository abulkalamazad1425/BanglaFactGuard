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
from typing import Any, Callable

import httpx
import structlog

from app.core.constants import SubmissionStatus
from app.core.exceptions import PermanentJobError, SourceNotFoundError
from app.db.engine import AsyncSessionLocal
from app.features.cache.cache_service import CacheService
from app.features.nlp.embedding_service import EmbeddingService
from app.features.nlp.ner_service import NERService
from app.features.nlp.nli_service import NLIService
from app.features.notifications.service import notify_once
from app.features.photocard.ocr_service import BanglaOcrService, OcrEngineUnavailableError
from app.features.photocard.service import PhotoCardService
from app.features.photocard.storage_service import PhotoCardStorageService
from app.features.sources.repository import SourceRepository
from app.features.submissions.repository import (
    OcrExtractionRepository,
    RetrievedArticleV2Repository,
    SubmissionRepository,
)
from app.features.verification.job_repository import VerificationJobRepository
from app.features.verification.repository import ResultV2Repository
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
    ocr_service: BanglaOcrService | None = None
    photocard_storage: PhotoCardStorageService | None = None

    @classmethod
    def from_app_state(cls, state: Any) -> "JobDeps":
        return cls(
            cache_service=state.cache_service,
            embedding_service=state.embedding_service,
            ner_service=state.ner_service,
            nli_service=state.nli_service,
            http_client=state.http_client,
            ocr_service=getattr(state, "photocard_ocr", None),
            photocard_storage=getattr(state, "photocard_storage", None),
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
    force_refresh = bool((payload or {}).get("force_refresh"))
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

        result_repo = ResultV2Repository(session)
        article_repo = RetrievedArticleV2Repository(session)
        source_repo = SourceRepository(session)
        try:
            if kind == "PHOTO_CARD":
                service = PhotoCardService(
                    ocr_service=deps.ocr_service or BanglaOcrService(),
                    storage=deps.photocard_storage or PhotoCardStorageService(),
                    submission_repo=submission_repo,
                    ocr_repo=OcrExtractionRepository(session),
                    result_repo=result_repo,
                    article_repo=article_repo,
                    source_repo=source_repo,
                    cache_service=deps.cache_service,
                    embedding_service=deps.embedding_service,
                    ner_service=deps.ner_service,
                    nli_service=deps.nli_service,
                    http_client=deps.http_client,
                )
                await service.process_submission(submission_id, force_refresh=force_refresh)
            else:
                service = VerificationService(
                    submission_repo=submission_repo,
                    result_repo=result_repo,
                    article_repo=article_repo,
                    source_repo=source_repo,
                    cache_service=deps.cache_service,
                    embedding_service=deps.embedding_service,
                    ner_service=deps.ner_service,
                    nli_service=deps.nli_service,
                    http_client=deps.http_client,
                )
                # Visible PROCESSING/VERIFYING before the slow part starts.
                await submission_repo.mark_processing(submission_id)
                await submission_repo.set_phase(submission_id, "VERIFYING")
                await session.commit()
                await service.run_for_submission(submission_id, force_refresh=force_refresh)
            await session.commit()
        except SourceNotFoundError as exc:
            await session.rollback()
            raise PermanentJobError(
                f"The claimed source could not be resolved: {exc.claimed_source!r}"
            ) from exc
        except Exception:
            await session.rollback()
            raise


class VerificationJobWorker:
    """Drains ``verification_jobs`` with bounded concurrency."""

    def __init__(
        self,
        deps: JobDeps,
        *,
        session_factory: Callable[[], Any] = AsyncSessionLocal,
        concurrency: int = 2,
        poll_interval_s: float = 5.0,
        stale_after_s: float = 120.0,
        heartbeat_interval_s: float = 30.0,
        runner: Callable[..., Any] | None = None,
    ) -> None:
        self.deps = deps
        self._session_factory = session_factory
        self._concurrency = concurrency
        self._poll = poll_interval_s
        self._stale_after = stale_after_s
        self._heartbeat_every = heartbeat_interval_s
        self._runner = runner or execute_job
        self._worker_id = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:6]}"
        self._wake = asyncio.Event()
        self._stop = False
        self._loop_task: asyncio.Task | None = None
        self._inflight: set[asyncio.Task] = set()
        self._slots: asyncio.Semaphore | None = None

    # ── lifecycle ────────────────────────────────────────────────────────

    def start(self) -> None:
        if self._loop_task is None:
            self._stop = False
            self._slots = asyncio.Semaphore(self._concurrency)
            self._loop_task = asyncio.create_task(self._run_loop(), name="verification-job-worker")
            logger.info("job_worker_started", worker_id=self._worker_id, concurrency=self._concurrency)

    async def stop(self) -> None:
        self._stop = True
        self._wake.set()
        if self._loop_task:
            self._loop_task.cancel()
            await asyncio.gather(self._loop_task, return_exceptions=True)
        for t in list(self._inflight):
            t.cancel()
        await asyncio.gather(*self._inflight, return_exceptions=True)
        self._loop_task = None

    def wake(self) -> None:
        """Poke the worker after enqueueing; purely a latency optimisation."""
        self._wake.set()

    # ── loop ─────────────────────────────────────────────────────────────

    async def _run_loop(self) -> None:
        assert self._slots is not None
        while not self._stop:
            try:
                await self._slots.acquire()
                job = await self._claim()
                if job is None:
                    self._slots.release()
                    self._wake.clear()
                    try:
                        await asyncio.wait_for(self._wake.wait(), timeout=self._poll)
                    except asyncio.TimeoutError:
                        pass
                    continue
                task = asyncio.create_task(self._run_job(job))
                self._inflight.add(task)
                task.add_done_callback(self._inflight.discard)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - the loop must survive anything
                self._slots.release()
                logger.error("job_worker_loop_error", error=str(exc)[:200])
                await asyncio.sleep(self._poll)

    async def _claim(self) -> dict | None:
        async with self._session_factory() as session:
            repo = VerificationJobRepository(session)
            job = await repo.claim_next(self._worker_id, stale_after_s=self._stale_after)
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

    async def _run_job(self, job: dict) -> None:
        assert self._slots is not None
        log = logger.bind(job_id=str(job["id"]), submission_id=str(job["submission_id"]), kind=job["kind"])
        heartbeat = asyncio.create_task(self._heartbeat(job["id"]))
        try:
            log.info("verification_job_started", attempt=job["attempts"])
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
        except OcrEngineUnavailableError as exc:
            await self._fail(job, exc.message, permanent=False)
        except Exception as exc:  # noqa: BLE001
            log.error("verification_job_failed", error=str(exc)[:200])
            await self._fail(job, "Verification could not be completed. Please try again.", permanent=False, error=str(exc))
        finally:
            heartbeat.cancel()
            self._slots.release()

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
                    await SubmissionRepository(session).set_phase(job["submission_id"], "QUEUED")
                await session.commit()
        except Exception as exc:  # noqa: BLE001
            logger.error("job_fail_handling_error", error=str(exc)[:200])
            # The row stays RUNNING with a stale heartbeat and will be reclaimed.
