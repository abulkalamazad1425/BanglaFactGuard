"""
Photo-card verification - accepted fast, processed in the background.

Flow
----
1. ``accept_upload``  validates the inputs, durably stores the image bytes,
   creates a PHOTO_CARD submission (owner, claimed source/date, OCR record
   holding the image key) and its durable job row in ONE transaction, and
   returns. Nothing slow (OCR, Gemini, retrieval, ML) runs on the request.
2. ``process_submission`` is what the job worker runs, with its own DB
   session: load the stored image -> OCR -> Gemini headline extraction (the
   existing deterministic extractor on any failure / invalid / unusable
   output) -> the shared 12-stage pipeline against the extracted headline and
   the USER'S claimed source/date. Image-detected source/date are
   supplementary metadata and never override the user's values.

A photo card is ALWAYS verified HEADLINE_ONLY: only the extracted headline is
used - no synthetic body, no confirmation step. Extraction failure is a FAILED
submission with a reason; it is never reported as Source Not Found or Content
Altered, because no automated check ran.

``verify`` (synchronous endpoint) is kept for compatibility and reuses the very
same two steps inline.
"""

from __future__ import annotations

import re
import uuid
from datetime import date

import httpx
import structlog

from app.core.config import get_settings
from app.core.constants import ClaimScope, SubmissionStatus, SubmissionType
from app.core.exceptions import (
    ImageStorageUnavailableError,
    PermanentJobError,
    PhotoCardExtractionFailedError,
    SourceNotFoundError,
)
from app.features.cache.cache_service import CacheService
from app.features.nlp.embedding_service import EmbeddingService
from app.features.nlp.ner_service import NERService
from app.features.nlp.nli_service import NLIService
from app.features.notifications.service import notify_once
from app.features.photocard.claim_extractor import normalize_for_match
from app.features.photocard.gemini_extractor import HeadlineExtraction, extract_headline
from app.features.photocard.ocr_service import (
    BanglaOcrService,
    OcrFailedError,
)
from app.features.photocard.schemas import (
    DetectedSourceSchema,
    PhotoCardAcceptedResponse,
    PhotoCardResultResponse,
    PhotoCardVerifyResponse,
)
from app.features.photocard.source_detector import DetectedSource, SourceDetector
from app.features.photocard.storage_service import PhotoCardStorageService
from app.features.sources.repository import SourceRepository
from app.features.sources.resolution import resolve_claimed_source
from app.features.submissions.models import OcrExtraction, Submission
from app.features.submissions.repository import (
    OcrExtractionRepository,
    RetrievedArticleV2Repository,
    SubmissionRepository,
)
from app.features.verification.job_repository import VerificationJobRepository
from app.features.verification.pipeline.context import build_context
from app.features.verification.pipeline.factory import build_verification_stages
from app.features.verification.pipeline.orchestrator import PipelineOrchestrator
from app.features.verification.presenter import load_verification_response
from app.features.verification.repository import ResultV2Repository
from app.features.verification.reuse import ResultReuseService
from app.shared.utils.bangla_normalizer import normalize_bangla_digits
from app.shared.utils.hashing import compute_claim_hash

logger = structlog.get_logger(__name__)
_SETTINGS = get_settings()


class PhotoCardService:
    """Unattended extraction and verification for photo-card submissions."""

    def __init__(
        self,
        *,
        ocr_service: BanglaOcrService,
        storage: PhotoCardStorageService,
        submission_repo: SubmissionRepository,
        ocr_repo: OcrExtractionRepository,
        result_repo: ResultV2Repository,
        article_repo: RetrievedArticleV2Repository,
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
        """OCR -> headline extraction -> shared pipeline for a stored card.

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
        ocr_record = await self.ocr_repo.get_by_submission_id(submission_id)
        if ocr_record is None or not ocr_record.image_object_key:
            raise PermanentJobError("The uploaded card image is missing.")

        claimed_source_text = submission.claimed_source_text or ""
        published_date = submission.published_date
        canonical = await resolve_claimed_source(claimed_source_text, self.source_repo)
        if canonical is None:
            raise PermanentJobError(f"The claimed source could not be resolved: {claimed_source_text!r}")

        log = logger.bind(submission_id=str(submission_id))

        # Committed immediately so polling clients and My Submissions show
        # PROCESSING/EXTRACTING while the slow work runs.
        await self.submission_repo.mark_processing(submission_id)
        await self.submission_repo.set_phase(submission_id, "EXTRACTING")
        await session.commit()

        image_bytes = await self.storage.download(ocr_record.image_object_key)
        if not image_bytes:
            raise RuntimeError("stored card image could not be read back")  # retryable

        try:
            ocr_output = await self.ocr_service.recognize(image_bytes)
        except OcrFailedError as exc:
            raise PermanentJobError(
                "No readable Bangla text could be found in the image. Try a sharper or less cluttered image."
            ) from exc

        detector = SourceDetector(self.source_repo)
        detections = await detector.detect(
            ocr_output.text, threshold=_SETTINGS.ocr.source_match_threshold
        )
        extraction = await extract_headline(
            ocr_output.text,
            raw_lines=[(line.text, line.confidence) for line in ocr_output.lines],
            source_names=_source_names(detections),
            http_client=self.http_client,
            min_bangla_ratio=_SETTINGS.ocr.min_line_bangla_ratio,
            min_confidence=_SETTINGS.ocr.min_line_confidence,
        )

        conflict_warnings = _detect_conflicts(extraction, claimed_source_text, published_date)
        all_warnings = [*extraction.warnings, *conflict_warnings]

        # Persist OCR + provenance regardless of extraction outcome.
        ocr_record.raw_extracted_text = ocr_output.text
        ocr_record.ocr_confidence = _clamp(ocr_output.confidence)
        ocr_record.ocr_engine = f"{ocr_output.engine}:{ocr_output.variant}"[:100]
        ocr_record.extractor_used = extraction.extractor_used
        ocr_record.extraction_model_version = extraction.model_version
        ocr_record.extraction_warnings = all_warnings
        ocr_record.detected_source_text = extraction.detected_source_text
        ocr_record.detected_date_text = extraction.detected_date_text

        if not extraction.is_usable:
            log.warning(
                "photocard_extraction_failed",
                extractor_used=extraction.extractor_used,
                warnings=extraction.warnings,
            )
            await session.commit()
            # Explicit extraction failure - never Source Not Found / Altered.
            raise PermanentJobError(
                "Could not extract a readable headline from this photo card. "
                "Try a sharper or less cluttered image.",
                details={"warnings": extraction.warnings},
            )

        submission.headline = extraction.headline[:2000]
        submission.content_hash = compute_claim_hash(
            extraction.headline,
            canonical,
            ClaimScope.HEADLINE_ONLY,
            published_date=published_date,
        )
        await self.submission_repo.set_phase(submission_id, "VERIFYING")
        await session.commit()

        # Photo cards are ALWAYS headline-only: no body, nothing synthesised.
        context = build_context(
            headline=extraction.headline,
            claimed_source=claimed_source_text,
            published_date=published_date,
            force_refresh=force_refresh,
            submission_id=submission_id,
            submitter_id=submission.submitter_id,
            claim_scope=ClaimScope.HEADLINE_ONLY,
        )
        orchestrator = PipelineOrchestrator(
            stages=self._build_stages(), submission_repo=self.submission_repo
        )
        context = await orchestrator.run(context)

        if context.cache_hit and context.reused_from_submission_id:
            # An identical fresh, complete verification exists: copy its
            # automated result onto THIS submission. The photo-card
            # submission, its image/OCR record and its owner are untouched.
            source = await self.submission_repo.get_by_id(context.reused_from_submission_id)
            source_result = await self.result_repo.get_by_submission_id(source.id)
            if source_result is not None and source.id != submission.id:
                await self.reuse.materialize(
                    source=source, source_result=source_result, target=submission
                )
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
        log.info("photocard_processed", cache_hit=context.cache_hit)

    # ── synchronous endpoint (compatibility) ─────────────────────────────

    async def verify(
        self,
        *,
        image_bytes: bytes,
        original_filename: str,
        claimed_source_text: str,
        published_date: date | None,
        force_refresh: bool = False,
        submitter_id: uuid.UUID | None = None,
    ) -> PhotoCardVerifyResponse:
        submission = await self.accept_upload(
            image_bytes=image_bytes,
            original_filename=original_filename,
            claimed_source_text=claimed_source_text,
            published_date=published_date,
            force_refresh=force_refresh,
            submitter_id=submitter_id,
            enqueue=False,
        )
        try:
            await self.process_submission(submission.id, force_refresh=force_refresh)
        except PermanentJobError as exc:
            await self.submission_repo.mark_failed(submission.id, exc.reason)
            ocr = await self.ocr_repo.get_by_submission_id(submission.id)
            raise PhotoCardExtractionFailedError(
                ocr.raw_extracted_text if ocr else "", list(exc.details.get("warnings", []))
            ) from exc

        result = await self.get_result(submission.id)
        assert result is not None and result.verification is not None
        v = result.verification
        return PhotoCardVerifyResponse(
            submission_id=submission.id,
            verification=v,
            extracted_headline=result.headline or "",
            extractor_used=result.extractor_used or "EXISTING_FALLBACK",
            extraction_model_version=result.extraction_model_version,
            extraction_warnings=result.extraction_warnings,
            detected_sources=[],
            detected_source_text=result.detected_source_text,
            detected_date_text=result.detected_date_text,
            source_date_conflict=bool(result.extraction_warnings),
            ocr_raw_text=result.ocr_raw_text or "",
            ocr_engine=result.ocr_engine or "unknown",
            ocr_confidence=result.ocr_confidence,
            image_url=result.image_url,
            claimed_source_text=claimed_source_text,
            published_date=published_date,
            reused_previous_result=v.cached,
            original_submission_id=None,
        )

    def _build_stages(self) -> list:
        """The verification pipeline, assembled exactly as ``/verify`` builds it."""
        return build_verification_stages(
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

        ocr_record = await self.ocr_repo.get_by_submission_id(submission_id)
        verification = await load_verification_response(
            submission, result_repo=self.result_repo, article_repo=self.article_repo
        )
        original_status = None
        if submission.duplicate_of_submission_id:
            original = await self.submission_repo.get_by_id_or_none(submission.duplicate_of_submission_id)
            original_status = original.status if original else None
        from app.features.verification.presenter import effective_status

        warnings = list(ocr_record.extraction_warnings or []) if ocr_record else []
        return PhotoCardResultResponse(
            submission_id=submission.id,
            status=effective_status(submission, original_status),
            phase=submission.processing_phase,
            failure_reason=submission.failure_reason,
            claim_scope=ClaimScope.HEADLINE_ONLY,
            headline=submission.headline,
            claimed_source_text=submission.claimed_source_text,
            published_date=submission.published_date,
            ocr_raw_text=(ocr_record.raw_extracted_text or None) if ocr_record else None,
            ocr_engine=(ocr_record.ocr_engine if ocr_record and ocr_record.ocr_engine != "pending" else None),
            ocr_confidence=ocr_record.ocr_confidence if ocr_record else None,
            image_url=await self._image_url(ocr_record),
            extractor_used=ocr_record.extractor_used if ocr_record else None,
            extraction_model_version=ocr_record.extraction_model_version if ocr_record else None,
            extraction_warnings=warnings,
            detected_source_text=ocr_record.detected_source_text if ocr_record else None,
            detected_date_text=ocr_record.detected_date_text if ocr_record else None,
            source_date_conflict=any("does not" in w and "match" in w for w in warnings),
            verification=verification,
            created_at=submission.created_at,
        )

    async def _image_url(self, ocr_record: OcrExtraction | None) -> str | None:
        if ocr_record is None or not ocr_record.image_object_key:
            return None
        return await self.storage.get_presigned_url(ocr_record.image_object_key)


def _to_source_schema(detection: DetectedSource) -> DetectedSourceSchema:
    return DetectedSourceSchema(
        source_id=uuid.UUID(detection.source_id),
        canonical_name=detection.canonical_name,
        display_name=detection.display_name,
        display_name_en=detection.display_name_en,
        confidence=detection.confidence,
        matched_text=detection.matched_text,
        method=detection.method,
    )


def _source_names(detections: list[DetectedSource]) -> list[str]:
    """Every surface form of the detected outlets, for banner stripping.

    Includes ``matched_text`` — the fragment OCR actually produced — so a
    garbled wordmark is removed using the garbled spelling, not only the
    canonical one.
    """
    names: list[str] = []
    for detection in detections:
        names.extend(
            [
                detection.display_name,
                detection.display_name_en or "",
                detection.canonical_name,
                detection.matched_text,
            ]
        )
    return [name for name in names if name]


def _detect_conflicts(
    extraction: HeadlineExtraction,
    claimed_source_text: str,
    published_date: date | None,
) -> list[str]:
    """Image-detected source/date text is preserved and surfaced, never used
    to silently override the user's own claimed_source_text/published_date.
    When the two disagree, that disagreement is recorded here rather than
    resolved — see docs/06-ai-engineering-design.md photo-card section."""
    conflicts: list[str] = []

    if extraction.detected_source_text and _source_text_conflicts(
        extraction.detected_source_text, claimed_source_text
    ):
        conflicts.append(
            f'The card\'s own text suggests the source "{extraction.detected_source_text}", '
            f'which does not match the claimed source "{claimed_source_text}" provided. '
            "Verification proceeded against the claimed source; this discrepancy is "
            "recorded for expert review."
        )

    if (
        extraction.detected_date_text
        and published_date is not None
        and _date_text_conflicts(extraction.detected_date_text, published_date)
    ):
        conflicts.append(
            f'The card\'s own text suggests a date ("{extraction.detected_date_text}") '
            f"that does not clearly match the published date ({published_date.isoformat()}) "
            "provided. Verification proceeded against the provided published date; this "
            "discrepancy is recorded for expert review."
        )

    return conflicts


def _source_text_conflicts(detected: str, claimed: str) -> bool:
    detected_norm = normalize_for_match(detected)
    claimed_norm = normalize_for_match(claimed)
    if not detected_norm or not claimed_norm:
        return False
    return detected_norm not in claimed_norm and claimed_norm not in detected_norm


def _date_text_conflicts(detected_text: str, published: date) -> bool:
    """Best-effort and deliberately conservative: this is a presence check,
    not a date parser. It only flags a conflict when the published date's
    year does not appear anywhere in the detected text at all — a card
    whose visible date text doesn't even share a year with what the user
    entered is worth an expert's attention; anything short of that is too
    easy to get wrong with text-only heuristics across date formats and is
    left unflagged rather than risk a false positive."""
    digits = re.sub(r"[^0-9]", "", normalize_bangla_digits(detected_text))
    if not digits:
        return False
    return str(published.year) not in digits


def _clamp(value: float | None) -> float | None:
    """Confidences are persisted under a 0–1 CHECK constraint."""
    if value is None:
        return None
    return max(0.0, min(1.0, float(value)))
