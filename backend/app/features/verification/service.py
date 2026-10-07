from __future__ import annotations

import uuid

import httpx
import structlog

from app.core.constants import ClaimScope, JobPhase, SubmissionStatus, SubmissionType
from app.core.exceptions import PipelineError, SourceNotFoundError
from app.features.cache.cache_service import CacheService
from app.features.nlp.embedding_service import EmbeddingService
from app.features.nlp.ner_service import NERService
from app.features.nlp.nli_service import NLIService
from app.features.notifications.service import notify_preliminary_result
from app.features.sources.repository import SourceRepository
from app.features.sources.resolution import resolve_claimed_source
from app.features.submissions.models import Submission
from app.features.submissions.repository import (
    RetrievedArticleRepository,
    SubmissionRepository,
)
from app.features.verification.job_repository import VerificationJobRepository
from app.features.verification.pipeline.context import PipelineContext, build_context
from app.features.verification.pipeline.factory import build_verification_stages
from app.features.verification.pipeline.orchestrator import PipelineOrchestrator
from app.features.verification.presenter import load_verification_response
from app.features.verification.repository import ResultRepository
from app.features.verification.reuse import ResultReuseService
from app.features.verification.schemas import VerificationRequest, VerificationResponse
from app.shared.utils.hashing import compute_claim_hash

logger = structlog.get_logger(__name__)


def claim_scope_for(body_text: str | None) -> ClaimScope:
    return (
        ClaimScope.HEADLINE_WITH_BODY
        if body_text and body_text.strip()
        else ClaimScope.HEADLINE_ONLY
    )


class VerificationService:

    def __init__(
        self,
        submission_repo: SubmissionRepository,
        result_repo: ResultRepository,
        article_repo: RetrievedArticleRepository,
        source_repo: SourceRepository,
        cache_service: CacheService,
        embedding_service: EmbeddingService,
        ner_service: NERService,
        nli_service: NLIService,
        http_client: httpx.AsyncClient,
    ) -> None:
        self.submission_repo = submission_repo
        self.result_repo = result_repo
        self.article_repo = article_repo
        self.source_repo = source_repo
        self.cache_service = cache_service
        self.embedding_service = embedding_service
        self.ner_service = ner_service
        self.nli_service = nli_service
        self.http_client = http_client
        self.reuse = ResultReuseService(submission_repo, result_repo)

    # ── synchronous run (also the body of the background job) ─────────────

    async def verify(
        self,
        request: VerificationRequest,
        *,
        submitter_id: uuid.UUID | None = None,
        submission_id: uuid.UUID | None = None,
    ) -> VerificationResponse:
        log = logger.bind(claimed_source_text=request.claimed_source_text)

        # Fail fast and explicitly: an unresolved source must not silently
        # fall through to an unrestricted, domain-unfiltered search.
        if await resolve_claimed_source(request.claimed_source_text, self.source_repo) is None:
            raise SourceNotFoundError(request.claimed_source_text)

        context = build_context(
            headline=request.headline,
            claimed_source=request.claimed_source_text,
            news_body=request.body_text,
            published_date=request.published_date,
            submitter_id=submitter_id,
            submission_id=submission_id,
        )
        log.info(
            "verification_started",
            request_id=str(context.request_id),
            headline_preview=request.headline[:80],
            scope=context.claim_scope.value,
        )

        orchestrator = PipelineOrchestrator(
            stages=self._build_stages(), submission_repo=self.submission_repo
        )
        context = await orchestrator.run(context)

        submission = await self._submission_for(context, request, submitter_id, submission_id)
        await self.result_repo.record_timings(
            submission.id, stage_ms=context.stage_timings,
            pipeline_ms=context.elapsed_ms, cache_hit=context.cache_hit,
        )
        response = await load_verification_response(
            submission, result_repo=self.result_repo, article_repo=self.article_repo
        )
        if response is None:
            raise PipelineError(
                message="Verification finished without a stored result.",
                details={"submission_id": str(submission.id)},
            )
        if not context.cache_hit:
            response = response.model_copy(update={"processing_time_ms": context.elapsed_ms})
        return response

    async def run_for_submission(self, submission_id: uuid.UUID) -> VerificationResponse:
        """Background-job entry point: everything comes from the stored
        submission row, nothing from a request."""
        submission = await self.submission_repo.get_by_id(submission_id)
        request = VerificationRequest(
            headline=submission.headline or "",
            body_text=submission.body_text,
            claimed_source_text=submission.claimed_source_text or "",
            published_date=submission.published_date,
        )
        return await self.verify(
            request, submitter_id=submission.submitter_id, submission_id=submission.id
        )

    async def _submission_for(
        self,
        context: PipelineContext,
        request: VerificationRequest,
        submitter_id: uuid.UUID | None,
        submission_id: uuid.UUID | None,
    ) -> Submission:
        """The requester's own submission, with its automated result."""
        if not context.cache_hit:
            return await self.submission_repo.get_by_id(context.submission_id)

        source = await self.submission_repo.get_by_id(context.reused_from_submission_id)
        source_result = await self.result_repo.get_by_submission_id(source.id)

        target: Submission | None = None
        if submission_id:
            target = await self.submission_repo.get_by_id_or_none(submission_id)
        if target is None:
            target = await self.submission_repo.create(
                Submission(
                    submission_type=SubmissionType.SOURCE_BASED,
                    headline=request.headline[:2000],
                    body_text=request.body_text or None,
                    claimed_source_text=request.claimed_source_text[:255],
                    published_date=request.published_date,
                    submitter_id=submitter_id,
                    content_hash=context.content_hash,
                    status=SubmissionStatus.PROCESSING,
                )
            )
        if target.id != source.id and source_result is not None:
            await self.reuse.materialize(source=source, source_result=source_result, target=target)
            if target.submitter_id:
                await notify_preliminary_result(
                    self.submission_repo.session,
                    user_id=target.submitter_id,
                    submission_id=target.id,
                    headline=target.headline,
                )
        return target

    # ── asynchronous registration ─────────────────────────────────────────

    async def register_claim(
        self,
        request: VerificationRequest,
        *,
        submitter_id: uuid.UUID | None = None,
    ) -> tuple[uuid.UUID, SubmissionStatus, bool]:
        """Accept a claim for background verification.

        Returns ``(submission_id, status, served_from_cache)``. The submission
        and its durable job row are committed together before returning, so an
        accepted claim can never be lost or stranded.

        A claim that was already checked is never verified again: if an
        identical, complete verification still exists in the database the
        requester gets their OWN submission carrying a copy of its automated
        result (no job queued, no new evidence search). Reuse never shares a
        submission across owners; only the same submitter's identical
        in-flight claim is handed back. A deleted submission/result is gone
        from the database and therefore never reused.
        """
        canonical = await resolve_claimed_source(request.claimed_source_text, self.source_repo)
        if canonical is None:
            raise SourceNotFoundError(request.claimed_source_text)

        scope = claim_scope_for(request.body_text)
        content_hash = compute_claim_hash(
            request.headline,
            canonical,
            scope,
            body=request.body_text,
            published_date=request.published_date,
        )

        found = await self.reuse.find_reusable(content_hash)
        if found is not None:
            source, source_result = found
            if source.submitter_id == submitter_id:
                logger.info("claim_served_from_existing_verification", submission_id=str(source.id))
                return source.id, source.status, True
            own = await self._create_submission(request, submitter_id, content_hash, SubmissionStatus.PROCESSING)
            await self.reuse.materialize(source=source, source_result=source_result, target=own)
            if own.submitter_id:
                await notify_preliminary_result(
                    self.submission_repo.session,
                    user_id=own.submitter_id,
                    submission_id=own.id,
                    headline=own.headline,
                )
            await self.submission_repo.session.commit()
            return own.id, SubmissionStatus.EXPERT_REVIEW, True

        in_flight = await self.submission_repo.get_in_flight_by_content_hash(content_hash)
        if in_flight is not None and in_flight.submitter_id == submitter_id:
            logger.info("claim_already_in_flight", submission_id=str(in_flight.id))
            return in_flight.id, in_flight.status, False

        submission = await self._create_submission(
            request, submitter_id, content_hash, SubmissionStatus.PENDING
        )
        submission.processing_phase = JobPhase.QUEUED.value
        await VerificationJobRepository(self.submission_repo.session).enqueue(
            submission.id, "SOURCE_BASED"
        )
        # Commit now: the worker looks the rows up by id and the caller starts
        # polling the moment the response lands.
        await self.submission_repo.session.commit()
        logger.info("claim_queued_for_verification", submission_id=str(submission.id))
        return submission.id, SubmissionStatus.PENDING, False

    async def _create_submission(
        self,
        request: VerificationRequest,
        submitter_id: uuid.UUID | None,
        content_hash: str,
        status: SubmissionStatus,
    ) -> Submission:
        return await self.submission_repo.create(
            Submission(
                submission_type=SubmissionType.SOURCE_BASED,
                headline=request.headline[:2000],
                body_text=request.body_text or None,
                claimed_source_text=request.claimed_source_text[:255],
                published_date=request.published_date,
                submitter_id=submitter_id,
                content_hash=content_hash,
                status=status,
            )
        )

    # ── read ──────────────────────────────────────────────────────────────

    async def get_result(self, submission_id: uuid.UUID) -> VerificationResponse | None:
        submission = await self.submission_repo.get_by_id_or_none(submission_id)
        if submission is None:
            return None
        # The database row is the single source of truth - identical after
        # Redis expiry, after navigating away, and via the cache fallback.
        return await load_verification_response(
            submission, result_repo=self.result_repo, article_repo=self.article_repo
        )

    def _build_stages(self) -> list:
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
