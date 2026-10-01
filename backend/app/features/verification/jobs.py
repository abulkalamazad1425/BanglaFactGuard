"""Background execution of the verification pipeline.

A source-based verification takes tens of seconds — long enough that holding
the HTTP request open forces the user to sit on the submit page until it
finishes. The API instead registers the claim, returns its id, and runs the
pipeline here, so the caller can navigate away and collect the result from
their history (or watch it land in place if they stay).

The request-scoped session is already closed by the time this runs, so the
job opens its own. The ML services and HTTP client are process-wide and are
passed in from ``app.state``.
"""

from __future__ import annotations

import asyncio
import uuid

import httpx
import structlog

from app.db.engine import AsyncSessionLocal
from app.features.cache.cache_service import CacheService
from app.features.nlp.embedding_service import EmbeddingService
from app.features.nlp.ner_service import NERService
from app.features.nlp.nli_service import NLIService
from app.features.sources.repository import SourceRepository
from app.features.submissions.repository import (
    RetrievedArticleV2Repository,
    SubmissionRepository,
)
from app.features.verification.repository import ResultV2Repository
from app.features.verification.schemas import VerificationRequest
from app.features.verification.service import VerificationService

logger = structlog.get_logger(__name__)

# asyncio only holds a weak reference to a bare task, so a job that nothing
# else awaits can be collected mid-flight. Keep a handle until it finishes.
_running: set[asyncio.Task] = set()

# Long enough for the queued-response socket write to complete.
_ACK_DRAIN_SECONDS = 0.25

# The pipeline shares the API's event loop and has CPU-bound stretches
# (embeddings, HTML parsing) that do not yield. Letting every queued claim
# start at once starves the loop: acknowledgements worth 0.15s of real work
# were taking seconds to reach the client. Run a couple at a time and let the
# rest wait their turn — they are already durable in the database, and the
# submitter is polling rather than holding a connection open.
_MAX_CONCURRENT_JOBS = 2
_job_slots: asyncio.Semaphore | None = None


def _slots() -> asyncio.Semaphore:
    # Built lazily so it binds to the running loop rather than import time.
    global _job_slots
    if _job_slots is None:
        _job_slots = asyncio.Semaphore(_MAX_CONCURRENT_JOBS)
    return _job_slots


def schedule_verification_job(**kwargs) -> None:
    """Hand the pipeline to the event loop without delaying the response."""
    task = asyncio.create_task(run_verification_job(**kwargs))
    _running.add(task)
    task.add_done_callback(_running.discard)


async def run_verification_job(
    *,
    submission_id: uuid.UUID,
    request: VerificationRequest,
    submitter_id: uuid.UUID | None,
    cache_service: CacheService,
    embedding_service: EmbeddingService,
    ner_service: NERService,
    nli_service: NLIService,
    http_client: httpx.AsyncClient,
) -> None:
    # Starting pipeline work in the same loop iteration that is still writing
    # the acknowledgement holds that response back, so yield first.
    await asyncio.sleep(_ACK_DRAIN_SECONDS)

    log = logger.bind(submission_id=str(submission_id))

    async with _slots():
        log.info("verification_job_started")

        async with AsyncSessionLocal() as session:
            submission_repo = SubmissionRepository(session)
            try:
                service = VerificationService(
                    submission_repo=submission_repo,
                    result_repo=ResultV2Repository(session),
                    article_repo=RetrievedArticleV2Repository(session),
                    source_repo=SourceRepository(session),
                    cache_service=cache_service,
                    embedding_service=embedding_service,
                    ner_service=ner_service,
                    nli_service=nli_service,
                    http_client=http_client,
                )
                response = await service.verify(
                    request,
                    submitter_id=submitter_id,
                    submission_id=submission_id,
                )
                await session.commit()
                log.info(
                    "verification_job_completed",
                    source_status=response.source_status.value,
                    content_status=(
                        response.content_status.value if response.content_status else None
                    ),
                    date_status=(
                        response.date_status.value if response.date_status else None
                    ),
                )
            except Exception as exc:
                await session.rollback()
                log.error("verification_job_failed", error=str(exc)[:200])
                # Leaving the row PENDING would strand the caller on a spinner
                # forever, so record the failure in its own transaction.
                try:
                    await submission_repo.mark_failed(submission_id)
                    await session.commit()
                except Exception as mark_exc:
                    await session.rollback()
                    log.error(
                        "verification_job_status_update_failed",
                        error=str(mark_exc)[:200],
                    )
