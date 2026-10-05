"""
Photo-card verification - accepted fast, processed in the background.

Flow
----
1. ``accept_upload`` validates the inputs, durably stores the image bytes,
   creates a PHOTO_CARD submission (owner, the USER'S claimed source/date,
   an extraction record holding the image key) and its durable job row in
   ONE transaction, and returns. Nothing slow runs on the request.
2. ``process_submission`` is what the job worker runs, with its own session:
   load the stored ORIGINAL image -> `PhotocardClaimExtractor` (Gemini image
   extraction, <= 3 attempts; after the last failure EasyOCR + the
   deterministic fallback extractor) -> the shared S01-S13 pipeline on the
   extracted headline with the USER'S selected source and claimed date.

The extracted date and source are raw, display-only metadata; they never
replace or get compared with the user's values. A photo card is ALWAYS
verified HEADLINE_ONLY. When every extraction path fails the submission is
FAILED with a reason - never reported as Source Not Found or as a headline
verdict, and no claim is fabricated.
"""

from __future__ import annotations

import time
import uuid
from datetime import date

import httpx
import structlog

from app.core.constants import ClaimScope, SubmissionStatus, SubmissionType
from app.core.exceptions import (
    ImageStorageUnavailableError,
    PermanentJobError,
    SourceNotFoundError,
)
from app.features.cache.cache_service import CacheService
from app.features.nlp.embedding_service import EmbeddingService
from app.features.nlp.ner_service import NERService
from app.features.nlp.nli_service import NLIService
from app.features.notifications.service import notify_once
from app.features.photocard.claim_extraction import PhotocardClaimExtractor, PhotocardExtraction
from app.features.photocard.ocr_service import BanglaOcrService
from app.features.photocard.schemas import PhotoCardAcceptedResponse, PhotoCardResultResponse
from app.features.photocard.storage_service import PhotoCardStorageService
from app.features.photocard.verification_stages import build_photocard_stages, compute_photocard_hash
from app.features.sources.repository import SourceRepository
from app.features.sources.resolution import resolve_claimed_source
from app.features.submissions.models import OcrExtraction, Submission
from app.features.submissions.repository import (
    OcrExtractionRepository,
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
        ocr_service: BanglaOcrService,
        storage: PhotoCardStorageService,
        submission_repo: SubmissionRepository,
        ocr_repo: OcrExtractionRepository,
        result_repo: ResultRepository,
        article_repo: RetrievedArticleRepository,
        source_repo: SourceRepository,
        cache_service: CacheService,
        embedding_service: EmbeddingService,
        ner_service: NERService,
        nli_service: NLIService,
        http_client: httpx.AsyncClient,
    ) -> None:
        self.ocr_service = ocr_service
        self.storage = storage
        self.submission_repo = submission_repo
        self.ocr_repo = ocr_repo
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
        claimed_source_text: str,
        published_date: date | None,
        force_refresh: bool = False,
        submitter_id: uuid.UUID | None = None,
        enqueue: bool = True,
    ) -> Submission:
        """Validate, durably store the image, and persist the submission +
        job. The caller acknowledges (HTTP 202) only after this returns."""
        canonical = await resolve_claimed_source(claimed_source_text, self.source_repo)
        if canonical is None:
            raise SourceNotFoundError(claimed_source_text)
        source = await self.source_repo.resolve_source(claimed_source_text)

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
                headline=None,  # unknown until extraction; a pending row renders without it
                body_text=None,
                claimed_source_text=claimed_source_text[:255],
                claimed_source_id=source.id if source else None,
                published_date=published_date,
                submitter_id=submitter_id,
                # Provisional, unique per submission: never collides with a
                # real claim identity. Replaced after extraction.
                content_hash=f"pending:{submission_id.hex}",
                status=SubmissionStatus.PENDING,
                processing_phase="QUEUED",
            )
        )
        await self.ocr_repo.create(
            OcrExtraction(
                submission_id=submission.id,
                image_object_key=object_key,
                raw_extracted_text="",
                confirmed_text=None,
                ocr_confidence=None,
                ocr_engine="pending",
                is_confirmed=False,
                extraction_warnings=[],
                fallback_used=False,
            )
        )
        if enqueue:
            await VerificationJobRepository(self.submission_repo.session).enqueue(
                submission.id, "PHOTO_CARD", payload={"force_refresh": bool(force_refresh)}
            )
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
                "Your card was received. You can leave this page - extraction and "
                "verification continue on the server; find the result in My Submissions."
            ),
            queued_at=submission.created_at,
        )

    # ── 2. process (job body) ────────────────────────────────────────────

    async def process_submission(
        self, submission_id: uuid.UUID, *, force_refresh: bool = False
    ) -> None:
        """Extraction -> shared pipeline for a stored card.

        Raises ``PermanentJobError`` for failures retrying cannot fix. Any
        other exception is retryable and is handled by the worker.
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
        record = await self.ocr_repo.get_by_submission_id(submission_id)
        if record is None or not record.image_object_key:
            raise PermanentJobError("The uploaded card image is missing.")

        claimed_source_text = submission.claimed_source_text or ""
        published_date = submission.published_date
        canonical = await resolve_claimed_source(claimed_source_text, self.source_repo)
        if canonical is None:
            raise PermanentJobError(f"The claimed source could not be resolved: {claimed_source_text!r}")

        log = logger.bind(submission_id=str(submission_id))
        await self.submission_repo.mark_processing(submission_id)
        await self.submission_repo.set_phase(submission_id, "EXTRACTING")
        await session.commit()

        preprocessing_ms: dict[str, int] = {}
        started = time.perf_counter()
        image_bytes = await self.storage.download(record.image_object_key)
        preprocessing_ms["image_download"] = int((time.perf_counter() - started) * 1000)
        if not image_bytes:
            raise RuntimeError("stored card image could not be read back")  # retryable

        extraction = await PhotocardClaimExtractor(
            ocr_service=self.ocr_service, source_repo=self.source_repo, http_client=self.http_client,
        ).extract(image_bytes)
        preprocessing_ms.update(extraction.timings_ms)
        self._store_extraction(record, extraction)

        if not extraction.is_usable:
            log.warning(
                "photocard_extraction_failed",
                gemini_attempts=extraction.gemini_attempts,
                fallback_used=extraction.fallback_used,
                reason=extraction.failure_reason,
            )
            await session.commit()
            raise PermanentJobError(
                "Could not extract a readable headline from this photo card. "
                "Try a sharper or less cluttered image.",
                details={"warnings": extraction.warnings, "reason": extraction.failure_reason},
            )

        submission.headline = extraction.headline[:2000]
        submission.content_hash = compute_photocard_hash(
            extraction.headline, canonical, published_date=published_date
        )
        await self.submission_repo.set_phase(submission_id, "VERIFYING")
        await session.commit()

        # Headline only; the USER'S source and date are the verification targets.
        context = build_context(
            headline=extraction.headline,
            claimed_source=claimed_source_text,
            published_date=published_date,
            force_refresh=force_refresh,
            submission_id=submission_id,
            submitter_id=submission.submitter_id,
            claim_scope=ClaimScope.HEADLINE_ONLY,
        )
        orchestrator = PipelineOrchestrator(stages=self._build_stages(), submission_repo=self.submission_repo)
        context = await orchestrator.run(context)

        if context.cache_hit and context.reused_from_submission_id:
            # Copy the identical, fresh, complete automated result onto THIS
            # submission; the card, its image and its owner are untouched.
            source = await self.submission_repo.get_by_id(context.reused_from_submission_id)
            source_result = await self.result_repo.get_by_submission_id(source.id)
            if source_result is not None and source.id != submission.id:
                await self.reuse.materialize(source=source, source_result=source_result, target=submission)
                if submission.submitter_id:
                    await notify_once(
                        session,
                        user_id=submission.submitter_id,
                        notification_type="VERIFICATION_COMPLETE",
                        link_url=f"/verify/{submission.id}",
                        title="Automated check complete (previous result reused)",
                        body=(
                            f'Your photo card "{(submission.headline or "")[:80]}" matches a claim '
                            "already checked; its preliminary automated result is shown."
                        ),
                    )
        await self.result_repo.record_timings(
            submission.id, stage_ms=context.stage_timings,
            pipeline_ms=context.elapsed_ms, preprocessing_ms=preprocessing_ms,
            cache_hit=context.cache_hit,
        )
        log.info("photocard_processed", method=extraction.method, cache_hit=context.cache_hit)

    @staticmethod
    def _store_extraction(record: OcrExtraction, extraction: PhotocardExtraction) -> None:
        """Raw extracted values and provenance; nothing is normalised here."""
        ocr = extraction.ocr_output
        record.raw_extracted_text = ocr.text if ocr else ""
        record.ocr_confidence = _clamp(ocr.confidence) if ocr else None
        record.ocr_engine = (f"{ocr.engine}:{ocr.variant}" if ocr else "not_run")[:100]
        record.extractor_used = extraction.method
        record.extraction_model_version = extraction.model_version
        record.extraction_attempts = extraction.gemini_attempts
        record.fallback_used = extraction.fallback_used
        record.extraction_warnings = list(extraction.warnings)
        record.extraction_details = {
            **extraction.diagnostics,
            "failure_reason": extraction.failure_reason,
            "headline": extraction.headline or None,
        }
        record.detected_source_text = extraction.source_text
        record.detected_date_text = extraction.date_text

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

        record = await self.ocr_repo.get_by_submission_id(submission_id)
        verification = await load_verification_response(
            submission, result_repo=self.result_repo, article_repo=self.article_repo
        )
        original_status = None
        if submission.duplicate_of_submission_id:
            original = await self.submission_repo.get_by_id_or_none(submission.duplicate_of_submission_id)
            original_status = original.status if original else None

        return PhotoCardResultResponse(
            submission_id=submission.id,
            status=effective_status(submission, original_status),
            phase=submission.processing_phase,
            failure_reason=submission.failure_reason,
            claim_scope=ClaimScope.HEADLINE_ONLY,
            headline=submission.headline,
            claimed_source_text=submission.claimed_source_text,
            published_date=submission.published_date,
            extraction_method=record.extractor_used if record else None,
            extraction_attempts=record.extraction_attempts if record else None,
            fallback_used=bool(record.fallback_used) if record else False,
            extraction_model_version=record.extraction_model_version if record else None,
            extraction_failures=extraction_failures(record.extraction_details if record else None),
            extraction_warnings=list(record.extraction_warnings or []) if record else [],
            extracted_date_text=record.detected_date_text if record else None,
            extracted_source_text=record.detected_source_text if record else None,
            ocr_raw_text=(record.raw_extracted_text or None) if record else None,
            ocr_engine=(record.ocr_engine if record and record.ocr_engine not in ("pending", "not_run") else None),
            ocr_confidence=record.ocr_confidence if record else None,
            image_url=await self._image_url(record),
            verification=verification,
            created_at=submission.created_at,
        )

    async def _image_url(self, ocr_record: OcrExtraction | None) -> str | None:
        if ocr_record is None or not ocr_record.image_object_key:
            return None
        return await self.storage.get_presigned_url(ocr_record.image_object_key)


_ATTEMPT_MESSAGES = {
    "timeout": "timed out",
    "network_error": "could not reach the service",
    "http_error": "the service returned an error",
    "permanent_error": "the request was rejected",
    "malformed_response": "returned an invalid response",
    "unusable_extraction": "did not return a readable headline",
}


def extraction_failures(details: dict | None) -> list[str]:
    """Short, user-presentable reasons for failed extraction attempts."""
    if not details:
        return []
    gemini = details.get("gemini") or {}
    out: list[str] = []
    if gemini.get("skipped_reason"):
        out.append("Image extraction was not available, so text recognition was used.")
    for attempt in gemini.get("attempts") or []:
        if attempt.get("outcome") != "success":
            out.append(f"Image extraction attempt {attempt.get('attempt')} "
                       f"{_ATTEMPT_MESSAGES.get(attempt.get('outcome'), 'failed')}.")
    if details.get("failure_reason"):
        out.append(details["failure_reason"])
    return out


def _clamp(value: float | None) -> float | None:
    """Confidences are persisted under a 0–1 CHECK constraint."""
    if value is None:
        return None
    return max(0.0, min(1.0, float(value)))
