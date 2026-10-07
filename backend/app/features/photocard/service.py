"""
Photo-card verification - image only, accepted fast, processed in the background.

Flow
----
1. ``accept_upload`` validates and durably stores the image, creates a
   PHOTO_CARD submission (owner; no headline, source or date yet), its
   extraction record holding the image key, and its durable job row in ONE
   transaction, and returns. Nothing slow runs on the request.
2. ``process_submission`` is what the job worker runs, with its own session:
   load the stored ORIGINAL image -> `PhotocardClaimExtractor` (Gemini with
   the active verified sources and their aliases, at most 9 requests) ->
   the extracted headline, verified source and printed date become the
   submission's claim -> the shared S01-S13 pipeline, HEADLINE_ONLY.

When every Gemini request fails, or a successful response lacks a headline
or an active verified source, the submission is FAILED with a user-facing
reason and verification never runs. There is no OCR and no fallback, and no
claim is fabricated.
"""

from __future__ import annotations

import time
import uuid

import httpx
import structlog

from app.core.constants import ClaimScope, JobPhase, SubmissionStatus, SubmissionType
from app.core.exceptions import ImageStorageUnavailableError, PermanentJobError
from app.features.cache.cache_service import CacheService
from app.features.nlp.embedding_service import EmbeddingService
from app.features.nlp.ner_service import NERService
from app.features.nlp.nli_service import NLIService
from app.features.notifications.service import notify_preliminary_result
from app.features.photocard.claim_extraction import (
    STATUS_PENDING,
    STATUS_SUCCEEDED,
    CardExtraction,
    PhotocardClaimExtractor,
)
from app.features.photocard.schemas import PhotoCardAcceptedResponse, PhotoCardResultResponse
from app.features.photocard.storage_service import PhotoCardStorageService
from app.features.photocard.verification_stages import build_photocard_stages, compute_photocard_hash
from app.features.sources.repository import SourceRepository
from app.features.submissions.models import PhotocardExtraction, Submission
from app.features.submissions.repository import (
    PhotocardExtractionRepository,
    RetrievedArticleRepository,
    SubmissionRepository,
)
from app.features.verification.job_repository import VerificationJobRepository
from app.features.verification.pipeline.context import build_context
from app.features.verification.pipeline.orchestrator import PipelineOrchestrator
from app.features.verification.presenter import effective_status, load_verification_response
from app.features.verification.repository import ResultRepository
from app.features.verification.reuse import ResultReuseService

logger = structlog.get_logger(__name__)


class PhotoCardService:
    """Unattended extraction and verification for photo-card submissions."""

    def __init__(
        self,
        *,
        storage: PhotoCardStorageService,
        submission_repo: SubmissionRepository,
        extraction_repo: PhotocardExtractionRepository,
        result_repo: ResultRepository,
        article_repo: RetrievedArticleRepository,
        source_repo: SourceRepository,
        cache_service: CacheService,
        embedding_service: EmbeddingService,
        ner_service: NERService,
        nli_service: NLIService,
        http_client: httpx.AsyncClient,
    ) -> None:
        self.storage = storage
        self.submission_repo = submission_repo
        self.extraction_repo = extraction_repo
        self.result_repo = result_repo
        self.article_repo = article_repo
        self.source_repo = source_repo
        self.cache_service = cache_service
        self.embedding_service = embedding_service
        self.ner_service = ner_service
        self.nli_service = nli_service
        self.http_client = http_client
        self.reuse = ResultReuseService(submission_repo, result_repo)

    # ── 1. accept (fast path) ────────────────────────────────────────────

    async def accept_upload(
        self,
        *,
        image_bytes: bytes,
        original_filename: str,
        submitter_id: uuid.UUID | None = None,
        enqueue: bool = True,
    ) -> Submission:
        """Durably store the image and persist the submission + job. The
        caller acknowledges (HTTP 202) only after this returns."""
        submission_id = uuid.uuid4()
        object_key = self.storage.build_object_key(submission_id, original_filename)
        if not await self.storage.upload(image_bytes, object_key):
            # The job reads the image back from storage, so an unstored image
            # cannot be accepted.
            raise ImageStorageUnavailableError()

        submission = await self.submission_repo.create(
            Submission(
                id=submission_id,
                submission_type=SubmissionType.PHOTO_CARD,
                # Headline, claimed source and date are read from the card.
                headline=None,
                body_text=None,
                claimed_source_text=None,
                claimed_source_id=None,
                published_date=None,
                submitter_id=submitter_id,
                # Provisional, unique per submission: never collides with a
                # real claim identity. Replaced after extraction.
                content_hash=f"pending:{submission_id.hex}",
                status=SubmissionStatus.PENDING,
                processing_phase=JobPhase.QUEUED.value,
            )
        )
        await self.extraction_repo.create(
            PhotocardExtraction(submission_id=submission.id, image_object_key=object_key, status=STATUS_PENDING)
        )
        if enqueue:
            await VerificationJobRepository(self.submission_repo.session).enqueue(submission.id, "PHOTO_CARD")
        await self.submission_repo.session.commit()
        logger.info(
            "photocard_accepted",
            submission_id=str(submission.id),
            submitter_id=str(submitter_id) if submitter_id else "anonymous",
            image_bytes=len(image_bytes),
        )
        return submission

    def accepted_response(self, submission: Submission) -> PhotoCardAcceptedResponse:
        return PhotoCardAcceptedResponse(
            submission_id=submission.id,
            status=submission.status,
            phase=submission.processing_phase,
            message=(
                "Your card was received. You can leave this page - the headline, news "
                "outlet and date are read and verified on the server; find the result "
                "in My Submissions."
            ),
            queued_at=submission.created_at,
        )

    # ── 2. process (job body) ────────────────────────────────────────────

    async def process_submission(self, submission_id: uuid.UUID) -> None:
        """Extraction -> shared pipeline for a stored card.

        Raises ``PermanentJobError`` for failures retrying cannot fix
        (including an exhausted Gemini budget: the job is never re-run, so a
        card never costs more than 9 Gemini requests). Any other exception is
        retryable and is handled by the worker.
        """
        session = self.submission_repo.session
        submission = await self.submission_repo.get_by_id(submission_id)
        if submission.submission_type != SubmissionType.PHOTO_CARD:
            raise PermanentJobError("Not a photo-card submission.")
        if submission.status in (
            SubmissionStatus.EXPERT_REVIEW,
            SubmissionStatus.FINALIZED,
            SubmissionStatus.ESCALATED,
        ):
            return  # already processed: idempotent re-run
        record = await self.extraction_repo.get_by_submission_id(submission_id)
        if record is None or not record.image_object_key:
            raise PermanentJobError("The uploaded card image is missing.")

        log = logger.bind(submission_id=str(submission_id))
        await self.submission_repo.mark_processing(submission_id)
        await self.submission_repo.set_phase(submission_id, JobPhase.EXTRACTING.value)
        await session.commit()

        preprocessing_ms: dict[str, int] = {}
        if record.status == STATUS_SUCCEEDED and submission.headline and submission.claimed_source_id:
            # A retry after a crash past extraction: never call Gemini twice.
            canonical = submission.claimed_source_text or ""
        else:
            started = time.perf_counter()
            image_bytes = await self.storage.download(record.image_object_key)
            preprocessing_ms["image_download"] = int((time.perf_counter() - started) * 1000)
            if not image_bytes:
                raise RuntimeError("stored card image could not be read back")  # retryable

            extraction = await PhotocardClaimExtractor(
                source_repo=self.source_repo, http_client=self.http_client,
            ).extract(image_bytes)
            preprocessing_ms.update(extraction.timings_ms)
            self._store_extraction(record, extraction)

            if not extraction.succeeded:
                log.warning("photocard_extraction_failed", status=extraction.status,
                            code=extraction.failure_code, attempts=extraction.attempts)
                await session.commit()
                raise PermanentJobError(
                    extraction.failure_message or "The photo card could not be read.",
                    details={"status": extraction.status, "code": extraction.failure_code},
                )

            # The extracted values ARE the claim - one representation, used
            # exactly as a typed claim's headline / outlet / date are.
            source = extraction.source
            canonical = source.canonical_name
            submission.headline = extraction.headline[:2000]
            submission.claimed_source_id = source.id
            submission.claimed_source_text = canonical[:255]
            submission.published_date = extraction.published_date
        submission.content_hash = compute_photocard_hash(
            submission.headline, canonical, published_date=submission.published_date
        )
        await self.submission_repo.set_phase(submission_id, JobPhase.VERIFYING.value)
        await session.commit()

        context = build_context(
            headline=submission.headline,
            claimed_source=canonical,
            published_date=submission.published_date,
            submission_id=submission_id,
            submitter_id=submission.submitter_id,
            claim_scope=ClaimScope.HEADLINE_ONLY,
        )
        orchestrator = PipelineOrchestrator(stages=self._build_stages(), submission_repo=self.submission_repo)
        context = await orchestrator.run(context)

        if context.cache_hit and context.reused_from_submission_id:
            # Copy the identical, complete automated result onto THIS
            # submission; the card, its image and its owner are untouched.
            source_sub = await self.submission_repo.get_by_id(context.reused_from_submission_id)
            source_result = await self.result_repo.get_by_submission_id(source_sub.id)
            if source_result is not None and source_sub.id != submission.id:
                await self.reuse.materialize(source=source_sub, source_result=source_result, target=submission)
                if submission.submitter_id:
                    await notify_preliminary_result(
                        session,
                        user_id=submission.submitter_id,
                        submission_id=submission.id,
                        headline=submission.headline,
                    )
        await self.result_repo.record_timings(
            submission.id, stage_ms=context.stage_timings,
            pipeline_ms=context.elapsed_ms, preprocessing_ms=preprocessing_ms,
            cache_hit=context.cache_hit,
        )
        log.info("photocard_processed", cache_hit=context.cache_hit)

    @staticmethod
    def _store_extraction(record: PhotocardExtraction, extraction: CardExtraction) -> None:
        record.status = extraction.status
        record.failure_code = extraction.failure_code
        record.model_version = (extraction.model_version or None) and extraction.model_version[:100]
        record.attempts = extraction.attempts
        record.extraction_details = extraction.details

    def _build_stages(self) -> list:
        """Shared retrieval with the photo-card-only content comparison policy."""
        return build_photocard_stages(
            submission_repo=self.submission_repo,
            result_repo=self.result_repo,
            article_repo=self.article_repo,
            source_repo=self.source_repo,
            cache_service=self.cache_service,
            embedding_service=self.embedding_service,
            ner_service=self.ner_service,
            nli_service=self.nli_service,
            http_client=self.http_client,
        )

    # ── retrieval ────────────────────────────────────────────────────────

    async def get_result(self, submission_id: uuid.UUID) -> PhotoCardResultResponse | None:
        """Current state by submission id: a pending/processing/failed card
        renders from the submission row; a completed one adds the saved
        verification (identical to what was shown right after it finished)."""
        submission = await self.submission_repo.get_by_id_or_none(submission_id)
        if submission is None or submission.submission_type != SubmissionType.PHOTO_CARD:
            return None

        record = await self.extraction_repo.get_by_submission_id(submission_id)
        verification = await load_verification_response(
            submission, result_repo=self.result_repo, article_repo=self.article_repo
        )
        original_status = None
        if submission.duplicate_of_submission_id:
            original = await self.submission_repo.get_by_id_or_none(submission.duplicate_of_submission_id)
            original_status = original.status if original else None

        source_name = None
        if submission.claimed_source_id:
            source = await self.source_repo.get_by_id_or_none(submission.claimed_source_id)
            source_name = source.display_name if source else None

        return PhotoCardResultResponse(
            submission_id=submission.id,
            status=effective_status(submission, original_status),
            phase=submission.processing_phase,
            failure_reason=submission.failure_reason,
            claim_scope=ClaimScope.HEADLINE_ONLY,
            headline=submission.headline,
            claimed_source_text=submission.claimed_source_text,
            claimed_source_name=source_name,
            published_date=submission.published_date,
            extraction_status=record.status if record else None,
            extraction_attempts=record.attempts if record else None,
            extraction_model_version=record.model_version if record else None,
            extraction_failures=extraction_failures(record.extraction_details if record else None),
            image_url=await self._image_url(record),
            verification=verification,
            created_at=submission.created_at,
        )

    async def _image_url(self, record: PhotocardExtraction | None) -> str | None:
        if record is None or not record.image_object_key:
            return None
        return await self.storage.get_presigned_url(record.image_object_key)


_ATTEMPT_MESSAGES = {
    "timeout": "timed out",
    "network_error": "could not reach the service",
    "http_error": "the service returned an error",
    "permanent_error": "the request was rejected",
    "quota_exhausted": "the daily image-reading limit has been reached",
    "malformed_response": "returned an invalid response",
}


def extraction_failures(details: dict | None) -> list[str]:
    """Short, user-presentable reasons for failed reading attempts."""
    if not details:
        return []
    out: list[str] = []
    if details.get("skipped_reason"):
        out.append("Every image-reading key has reached its limit for now."
                   if "limit" in details["skipped_reason"] else "Image reading is not available on this server.")
    for attempt in details.get("attempts") or []:
        if attempt.get("outcome") != "success":
            out.append(f"Image reading attempt {attempt.get('attempt')} "
                       f"{_ATTEMPT_MESSAGES.get(attempt.get('outcome'), 'failed')}.")
    return out
