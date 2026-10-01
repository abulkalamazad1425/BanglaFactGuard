"""
Photo-card verification — orchestration for the two-step flow.

**Step 1 — extract.** OCR the card, strip its chrome, segment a headline and
body, detect the claimed outlet from the branding, and persist a *draft*
submission the user has not yet confirmed. Nothing is verified yet.

**Step 2 — verify.** Take the text the user confirmed (they may have corrected
the OCR) and run it through the existing source-based verification pipeline,
unchanged. The photo card contributes the claim and the source; from there the
evidence retrieval, similarity analysis, contradiction detection and
classification are byte-for-byte the same logic that backs
``POST /verify`` — which is the point: a photo-card verdict has to be
defensible on the same terms as a typed claim.

The pipeline is driven directly rather than through ``VerificationService`` so
the draft submission's ID can be threaded into the context. That keeps the
submission typed ``PHOTO_CARD`` with its OCR record attached, instead of the
pipeline creating a second ``SOURCE_BASED`` row alongside it.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime

import httpx
import structlog

from app.core.constants import SourceStatus, SubmissionStatus, SubmissionType
from app.features.expert_review.overall_verdict import derive_ai_overall_verdict
from app.core.config import get_settings
from app.core.exceptions import BanglaFactGuardError, PermissionDeniedError
from app.features.cache.cache_service import CacheService
from app.features.nlp.embedding_service import EmbeddingService
from app.features.nlp.ner_service import NERService
from app.features.nlp.nli_service import NLIService
from app.features.photocard.claim_extractor import ExtractedClaim, extract_claim
from app.features.photocard.ocr_service import BanglaOcrService, bangla_ratio
from app.features.photocard.schemas import (
    DetectedSourceSchema,
    OcrLineSchema,
    PhotoCardExtractResponse,
    PhotoCardResultResponse,
    PhotoCardVerifyRequest,
    PhotoCardVerifyResponse,
)
from app.features.photocard.source_detector import DetectedSource, SourceDetector
from app.features.photocard.storage_service import PhotoCardStorageService
from app.features.search.duckduckgo_client import DuckDuckGoClient
from app.features.search.google_cse_client import GoogleCSEClient
from app.features.search.internal_site_client import InternalSiteSearchClient
from app.features.search.newsdata_client import NewsDataClient
from app.features.search.pygooglenews_client import PyGoogleNewsClient
from app.features.sources.repository import SourceRepository
from app.features.submissions.models import OcrExtraction, Submission
from app.features.submissions.repository import (
    OcrExtractionRepository,
    RetrievedArticleV2Repository,
    SubmissionRepository,
)
from app.features.verification.pipeline.context import PipelineContext, build_context
from app.features.verification.pipeline.orchestrator import PipelineOrchestrator
from app.features.verification.pipeline.stages.s01_normalizer import InputNormalizerStage
from app.features.verification.pipeline.stages.s02_cache_lookup import CacheLookupStage
from app.features.verification.pipeline.stages.s03_query_generator import (
    QueryGeneratorStage,
)
from app.features.verification.pipeline.stages.s04_source_search import SourceSearchStage
from app.features.verification.pipeline.stages.s05_evidence_retrieval import (
    EvidenceRetrievalStage,
)
from app.features.verification.pipeline.stages.s06_article_extractor import (
    ArticleExtractorStage,
)
from app.features.verification.pipeline.stages.s07_evidence_ranker import (
    EvidenceRankerStage,
)
from app.features.verification.pipeline.stages.s08_similarity_analyzer import (
    SimilarityAnalyzerStage,
)
from app.features.verification.pipeline.stages.s09_contradiction_detector import (
    ContradictionDetectorStage,
)
from app.features.verification.pipeline.stages.s10_manipulation_detector import (
    ManipulationDetectorStage,
)
from app.features.verification.pipeline.stages.s11_classifier import ClassifierStage
from app.features.verification.pipeline.stages.s12_persistence import PersistenceStage
from app.features.verification.repository import ResultV2Repository
from app.features.verification.schemas import (
    ManipulationFlagsSchema,
    VerificationResponse,
    VerificationScoresResponse,
)

logger = structlog.get_logger(__name__)
_SETTINGS = get_settings()


class PhotoCardDraftNotFoundError(BanglaFactGuardError):
    http_status_code = 404


class PhotoCardDraftStateError(BanglaFactGuardError):
    http_status_code = 409


class PhotoCardService:
    """Extraction and verification for photo-card submissions."""

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

    # ── Step 1: extract ──────────────────────────────────────────────────

    async def extract(
        self,
        *,
        image_bytes: bytes,
        original_filename: str,
        submitter_id: uuid.UUID | None = None,
    ) -> PhotoCardExtractResponse:
        """OCR a photo card and return a claim draft for user confirmation."""
        log = logger.bind(
            submitter_id=str(submitter_id) if submitter_id else "anonymous",
            image_bytes=len(image_bytes),
        )
        log.info("photocard_extract_started")

        ocr_output = await self.ocr_service.recognize(image_bytes)

        # Source detection runs first, and against the *raw* text: the outlet
        # banner is chrome as far as the claim is concerned, but it is exactly
        # the attribution signal needed here — and knowing which outlet it is
        # lets the extractor strip that banner out of the claim.
        detector = SourceDetector(self.source_repo)
        detections = await detector.detect(
            ocr_output.text, threshold=_SETTINGS.ocr.source_match_threshold
        )

        claim = extract_claim(
            [(line.text, line.confidence) for line in ocr_output.lines],
            min_bangla_ratio=_SETTINGS.ocr.min_line_bangla_ratio,
            min_confidence=_SETTINGS.ocr.min_line_confidence,
            source_names=_source_names(detections),
        )

        draft = await self._create_draft(
            image_bytes=image_bytes,
            claim=claim,
            detections=detections,
            submitter_id=submitter_id,
        )

        object_key = self.storage.build_object_key(draft.id, original_filename)
        uploaded = await self.storage.upload(image_bytes, object_key)

        await self.ocr_repo.create(
            OcrExtraction(
                submission_id=draft.id,
                image_object_key=object_key if uploaded else "",
                raw_extracted_text=ocr_output.text,
                confirmed_text=None,
                ocr_confidence=_clamp(ocr_output.confidence),
                ocr_engine=f"{ocr_output.engine}:{ocr_output.variant}"[:100],
                is_confirmed=False,
            )
        )

        image_url = (
            await self.storage.get_presigned_url(object_key) if uploaded else None
        )

        warnings = list(claim.warnings)
        if not uploaded:
            warnings.append(
                "The card image could not be stored, so no preview is available. "
                "Extraction and verification are unaffected."
            )
        if not detections:
            warnings.append(
                "No verified news source was detected on the card. Please select "
                "the claimed source manually."
            )

        primary = self._primary_source(detections)

        log.info(
            "photocard_extract_complete",
            draft_id=str(draft.id),
            engine=ocr_output.engine,
            kept_lines=len(claim.kept_lines),
            removed_lines=claim.removed_line_count,
            detected_source=primary.canonical_name if primary else None,
        )

        return PhotoCardExtractResponse(
            draft_id=draft.id,
            raw_text=ocr_output.text,
            cleaned_text=claim.cleaned_text,
            suggested_headline=claim.headline,
            suggested_body=claim.body,
            lines=[
                OcrLineSchema(
                    text=line.text,
                    confidence=_clamp(line.confidence),
                    bangla_ratio=line.bangla_ratio,
                    is_noise=line.is_noise,
                    noise_reason=line.noise_reason,
                )
                for line in claim.lines
            ],
            removed_line_count=claim.removed_line_count,
            detected_sources=[_to_source_schema(d) for d in detections],
            primary_source=_to_source_schema(primary) if primary else None,
            ocr_confidence=_clamp(ocr_output.confidence),
            ocr_engine=ocr_output.engine,
            bangla_char_ratio=bangla_ratio(ocr_output.text),
            image_url=image_url,
            warnings=warnings,
            created_at=draft.created_at,
        )

    async def _create_draft(
        self,
        *,
        image_bytes: bytes,
        claim: ExtractedClaim,
        detections: list[DetectedSource],
        submitter_id: uuid.UUID | None,
    ) -> Submission:
        """Persist the unconfirmed submission the draft flow hangs off.

        The provisional content hash is the image digest — the claim hash is
        not knowable until the user confirms the text, and S01 recomputes it
        from the confirmed headline and source on the verification run.
        """
        primary = self._primary_source(detections)
        claimed_source_id = uuid.UUID(primary.source_id) if primary else None

        return await self.submission_repo.create(
            Submission(
                submission_type=SubmissionType.PHOTO_CARD,
                headline=(claim.headline or None),
                body_text=claim.body,
                claimed_source_text=(
                    primary.canonical_name[:255] if primary else None
                ),
                claimed_source_id=claimed_source_id,
                submitter_id=submitter_id,
                content_hash=hashlib.sha256(image_bytes).hexdigest(),
                status=SubmissionStatus.PENDING,
            )
        )

    @staticmethod
    def _primary_source(detections: list[DetectedSource]) -> DetectedSource | None:
        if not detections:
            return None
        top = detections[0]
        if top.confidence < _SETTINGS.ocr.source_autoselect_threshold:
            return None
        return top

    # ── Step 2: verify ───────────────────────────────────────────────────

    async def verify(
        self,
        request: PhotoCardVerifyRequest,
        *,
        submitter_id: uuid.UUID | None = None,
    ) -> PhotoCardVerifyResponse:
        """Verify the confirmed claim against the claimed source."""
        draft = await self._load_draft(request.draft_id, submitter_id)
        ocr_record = await self.ocr_repo.get_by_submission_id(draft.id)

        log = logger.bind(
            draft_id=str(draft.id),
            claimed_source_text=request.claimed_source_text,
        )
        log.info("photocard_verify_started", headline_preview=request.headline[:80])

        source = await self.source_repo.resolve_source(request.claimed_source_text)

        await self.submission_repo.update(
            draft,
            headline=request.headline[:2000],
            body_text=request.body_text,
            claimed_source_text=request.claimed_source_text[:255],
            claimed_source_id=source.id if source else None,
            published_date=request.published_date,
        )

        if ocr_record is not None:
            await self.ocr_repo.update(
                ocr_record,
                confirmed_text=_join_confirmed(request.headline, request.body_text),
                is_confirmed=True,
            )

        context = build_context(
            headline=request.headline,
            claimed_source=request.claimed_source_text,
            news_body=request.body_text,
            published_date=request.published_date,
            force_refresh=request.force_refresh,
            submission_id=draft.id,
            submitter_id=submitter_id or draft.submitter_id,
        )

        orchestrator = PipelineOrchestrator(
            stages=self._build_stages(),
            submission_repo=self.submission_repo,
        )
        context = await orchestrator.run(context)

        # Duplicate detection (S02) redirects the context at an already-verified
        # submission and short-circuits the rest of the pipeline, leaving this
        # draft with nothing written to it. Drop the orphan, exactly as the
        # source-based flow never creates one for a duplicate claim.
        reused = bool(context.cache_hit and context.submission_id != draft.id)
        if reused:
            log.info(
                "photocard_duplicate_detected",
                original_submission_id=str(context.submission_id),
            )
            await self.submission_repo.delete(draft)

        verification = self._build_verification_response(context)
        image_url = await self._image_url(ocr_record)

        return PhotoCardVerifyResponse(
            submission_id=verification.submission_id,
            verification=verification,
            confirmed_headline=request.headline,
            confirmed_body=request.body_text,
            ocr_raw_text=ocr_record.raw_extracted_text if ocr_record else "",
            ocr_engine=ocr_record.ocr_engine if ocr_record else "unknown",
            ocr_confidence=ocr_record.ocr_confidence if ocr_record else None,
            image_url=image_url,
            reused_previous_result=reused,
            original_submission_id=context.submission_id if reused else None,
        )

    async def _load_draft(
        self, draft_id: uuid.UUID, submitter_id: uuid.UUID | None
    ) -> Submission:
        draft = await self.submission_repo.get_by_id_or_none(draft_id)
        if draft is None:
            raise PhotoCardDraftNotFoundError(
                message="Photo-card draft not found. Upload the card again.",
                details={"draft_id": str(draft_id)},
            )
        if draft.submission_type != SubmissionType.PHOTO_CARD:
            raise PhotoCardDraftStateError(
                message="That submission is not a photo-card draft.",
                details={"draft_id": str(draft_id)},
            )
        if draft.status not in (SubmissionStatus.PENDING, SubmissionStatus.FAILED):
            raise PhotoCardDraftStateError(
                message=(
                    "This photo card has already been verified. Open its report "
                    "instead of confirming it again."
                ),
                details={"draft_id": str(draft_id), "status": draft.status.value},
            )
        # Anonymous drafts stay claimable by whoever holds the draft id; a draft
        # created while signed in belongs to that account only.
        if draft.submitter_id is not None and draft.submitter_id != submitter_id:
            raise PermissionDeniedError()
        return draft

    def _build_stages(self) -> list:
        """The verification pipeline, assembled exactly as ``/verify`` builds it."""
        return [
            InputNormalizerStage(source_repo=self.source_repo),
            CacheLookupStage(
                cache_service=self.cache_service,
                submission_repo=self.submission_repo,
                result_repo=self.result_repo,
            ),
            QueryGeneratorStage(),
            SourceSearchStage(
                newsdata_client=NewsDataClient(self.http_client),
                google_cse_client=GoogleCSEClient(self.http_client),
                pygooglenews_client=PyGoogleNewsClient(),
                duckduckgo_client=DuckDuckGoClient(),
                internal_site_client=InternalSiteSearchClient(self.http_client),
                cache_service=self.cache_service,
            ),
            EvidenceRetrievalStage(http_client=self.http_client),
            ArticleExtractorStage(cache_service=self.cache_service),
            EvidenceRankerStage(embedding_service=self.embedding_service),
            SimilarityAnalyzerStage(
                embedding_service=self.embedding_service,
                ner_service=self.ner_service,
            ),
            ContradictionDetectorStage(nli_service=self.nli_service),
            ManipulationDetectorStage(embedding_service=self.embedding_service),
            ClassifierStage(),
            PersistenceStage(
                submission_repo=self.submission_repo,
                result_repo=self.result_repo,
                article_repo=self.article_repo,
                cache_service=self.cache_service,
                session=self.submission_repo.session,
            ),
        ]

    @staticmethod
    def _build_verification_response(context: PipelineContext) -> VerificationResponse:
        if context.cache_hit:
            cached_source = context.cached_source_status or SourceStatus.NOT_FOUND
            cached_ai_overall = derive_ai_overall_verdict(
                cached_source, context.cached_content_status, context.cached_date_status
            )
            return VerificationResponse(
                submission_id=context.submission_id or uuid.uuid4(),
                # Reflects the AI's call at cache-write time, not whatever
                # expert review may have since finalized — get_result()/
                # _load_verification() below shows the authoritative value.
                overall_verdict=cached_ai_overall,
                is_finalized=False,
                ai_overall_verdict=cached_ai_overall,
                ai_source_status=cached_source,
                ai_content_status=context.cached_content_status,
                ai_date_status=context.cached_date_status,
                source_status=cached_source,
                content_status=context.cached_content_status,
                date_status=context.cached_date_status,
                confidence=context.cached_confidence or 0.0,
                reasoning=context.cached_reasoning or "",
                matched_articles=context.cached_matched_articles,
                scores=VerificationScoresResponse.model_validate(
                    (context.cached_scores or context.scores).model_dump()
                ),
                manipulation_flags=(
                    context.cached_manipulation_flags or context.manipulation_flags
                ),
                normalized_source=context.normalized_source,
                cached=True,
                processing_time_ms=None,
                created_at=datetime.utcnow(),
            )

        fresh_source = context.source_status or SourceStatus.NOT_FOUND
        fresh_ai_overall = derive_ai_overall_verdict(
            fresh_source, context.content_status, context.date_status
        )
        return VerificationResponse(
            submission_id=context.submission_id or uuid.uuid4(),
            overall_verdict=fresh_ai_overall,
            is_finalized=False,
            ai_overall_verdict=fresh_ai_overall,
            ai_source_status=fresh_source,
            ai_content_status=context.content_status,
            ai_date_status=context.date_status,
            source_status=fresh_source,
            content_status=context.content_status,
            date_status=context.date_status,
            confidence=context.confidence,
            reasoning=context.reasoning,
            matched_articles=context.ranked_articles[:3],
            scores=VerificationScoresResponse.model_validate(
                context.scores.model_dump()
            ),
            manipulation_flags=context.manipulation_flags,
            normalized_source=context.normalized_source,
            cached=False,
            processing_time_ms=context.elapsed_ms,
            created_at=datetime.utcnow(),
        )

    # ── Retrieval ────────────────────────────────────────────────────────

    async def get_result(
        self, submission_id: uuid.UUID
    ) -> PhotoCardResultResponse | None:
        """Load a stored photo-card report, verdict included when available."""
        submission = await self.submission_repo.get_by_id_or_none(submission_id)
        if submission is None:
            return None

        ocr_record = await self.ocr_repo.get_by_submission_id(submission_id)
        verification = await self._load_verification(submission)

        return PhotoCardResultResponse(
            submission_id=submission.id,
            status=submission.status,
            headline=submission.headline,
            body_text=submission.body_text,
            claimed_source_text=submission.claimed_source_text,
            published_date=submission.published_date,
            ocr_raw_text=ocr_record.raw_extracted_text if ocr_record else None,
            ocr_confirmed_text=ocr_record.confirmed_text if ocr_record else None,
            ocr_engine=ocr_record.ocr_engine if ocr_record else None,
            ocr_confidence=ocr_record.ocr_confidence if ocr_record else None,
            image_url=await self._image_url(ocr_record),
            verification=verification,
            created_at=submission.created_at,
        )

    async def _load_verification(
        self, submission: Submission
    ) -> VerificationResponse | None:
        from app.core.constants import SearchProvider
        from app.features.articles.schemas import RankedArticleSchema

        result = await self.result_repo.get_by_submission_id(submission.id)
        if result is None or result.source_status is None:
            return None

        articles = await self.article_repo.get_for_submission(
            submission.id, successful_only=True, order_by_rank=True, limit=3
        )

        is_finalized = bool(result.overall_verdict)
        ai_overall = derive_ai_overall_verdict(
            result.source_status, result.content_status, result.date_status
        )
        displayed_overall = result.overall_verdict or ai_overall

        return VerificationResponse(
            submission_id=submission.id,
            overall_verdict=displayed_overall,
            is_finalized=is_finalized,
            was_overridden=is_finalized and displayed_overall != ai_overall,
            ai_overall_verdict=ai_overall,
            ai_source_status=result.source_status,
            ai_content_status=result.content_status,
            ai_date_status=result.date_status,
            source_status=result.final_source_status or result.source_status,
            content_status=(result.final_content_status if is_finalized else result.content_status),
            date_status=(result.final_date_status if is_finalized else result.date_status),
            confidence=result.confidence or 0.0,
            reasoning=result.reasoning or "",
            matched_articles=[
                RankedArticleSchema(
                    url=article.url,
                    title=article.title,
                    author=article.author,
                    published_date=article.published_date,
                    body=article.body,
                    rank_score=article.rank_score or 0.0,
                    search_provider=SearchProvider.INTERNAL_SITE,
                    extraction_method=article.extraction_method,
                )
                for article in articles
            ],
            scores=VerificationScoresResponse(
                semantic_similarity=result.semantic_similarity,
                entity_match=result.entity_match,
                keyword_overlap=result.keyword_overlap,
                numerical_consistency=result.numerical_consistency,
                contradiction_score=result.contradiction_score,
            ),
            manipulation_flags=ManipulationFlagsSchema(),
            normalized_source=submission.claimed_source_text,
            cached=True,
            processing_time_ms=result.avg_verification_time_ms,
            created_at=result.created_at,
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


def _join_confirmed(headline: str, body: str | None) -> str:
    return f"{headline}\n\n{body}".strip() if body else headline.strip()


def _clamp(value: float | None) -> float | None:
    """Confidences are persisted under a 0–1 CHECK constraint."""
    if value is None:
        return None
    return max(0.0, min(1.0, float(value)))
