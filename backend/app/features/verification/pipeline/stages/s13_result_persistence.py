"""S13 - Result persistence, cache pointer and result delivery.

Responsibilities carried over from the former persistence stage:
  * idempotent re-run: a submission already in expert review keeps its saved
    automated result and is not notified twice;
  * retrieved articles (the selected source first) and search queries;
  * the automated result row (verdicts, statuses, correspondence
    measurements, full `analysis_details`);
  * hand-off to expert review (every automated result enters the queue) and
    the DONE phase;
  * the Redis claim pointer, only for a reusable (complete, current) result;
  * the submitter notification (`notify_preliminary_result`, never duplicated).
All writes share the caller's session/transaction; the job commits it.
"""

from __future__ import annotations

import uuid
from collections import Counter

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    VERIFICATION_PIPELINE_VERSION,
    JobPhase,
    PipelineStageID,
    SearchProvider,
    SubmissionStatus,
    SubmissionType,
)
from app.core.exceptions import PersistenceError
from app.features.cache.cache_service import CacheService
from app.features.notifications.service import notify_preliminary_result
from app.features.submissions.models import RetrievedArticle, SourceEvidenceQuery, Submission
from app.features.submissions.repository import RetrievedArticleRepository, SubmissionRepository
from app.features.verification.pipeline.context import PipelineContext
from app.features.verification.pipeline.stages.s02_cache_lookup import CacheLookupStage
from app.features.verification.repository import ResultRepository
from app.features.verification.reuse import result_is_reusable
from app.shared.utils.hashing import compute_url_hash

logger = structlog.get_logger(__name__)


class ResultPersistenceStage:

    stage_id = PipelineStageID.S13_RESULT_PERSISTENCE

    def __init__(
        self,
        submission_repo: SubmissionRepository,
        result_repo: ResultRepository,
        article_repo: RetrievedArticleRepository,
        cache_service: CacheService,
        session: AsyncSession | None = None,
    ) -> None:
        self.submission_repo = submission_repo
        self.result_repo = result_repo
        self.article_repo = article_repo
        self.cache_service = cache_service
        self.session = session or submission_repo.session

    async def execute(self, context: PipelineContext) -> PipelineContext:
        try:
            submission, already_done = await self._upsert_submission(context)
            context.submission_id = submission.id

            if already_done:
                existing = await self.result_repo.get_by_submission_id(submission.id)
                context.result_id = existing.id if existing else None
                context.persisted = True
                logger.info("s13_already_persisted_skipping", submission_id=str(submission.id))
                return context

            top_article_db_id = await self._persist_articles(context, submission.id)
            metrics = context.analysis.metrics
            ha = context.analysis.headline_alteration
            body = context.analysis.body_similarity

            def metric(name: str) -> float | None:
                d = metrics.get(name)
                return d.value if d is not None else None

            result = await self.result_repo.upsert_result(
                submission_id=submission.id,
                source_status=context.source_status,
                content_status=context.content_status,
                headline_check_status=context.headline_check_status.value if context.headline_check_status else None,
                headline_exact_match=ha.exact_match if ha and ha.verdict is not None else None,
                body_comparison_status=body.status.value if body else None,
                date_status=context.date_status,
                confidence=context.confidence,
                reasoning=context.reasoning,
                headline_similarity=metric("headline_title_similarity"),
                headline_keyword_coverage=metric("title_keyword_coverage"),
                passage_keyword_coverage=metric("passage_keyword_coverage"),
                top_article_id=top_article_db_id,
                avg_verification_time_ms=context.elapsed_ms,
                claim_scope=context.claim_scope.value,
                pipeline_version=VERIFICATION_PIPELINE_VERSION,
                analysis_details=context.analysis.model_dump(mode="json"),
            )
            context.result_id = result.id

            await self._persist_search_queries(context, submission.id)
            for stage, duration_ms in context.stage_timings.items():
                (logger.warning if stage in context.stage_errors else logger.info)(
                    "verification_stage_completed",
                    submission_id=str(submission.id),
                    stage=stage,
                    duration_ms=duration_ms,
                    error=context.stage_errors.get(stage),
                )

            # Every automated result enters expert review. No automated
            # overall verdict is derived or stored.
            await self.submission_repo.mark_ai_done(submission.id)
            await self.submission_repo.set_phase(submission.id, JobPhase.DONE.value)

            await self._write_cache_pointer(context, submission.id, result)
            await self._notify(submission, context)

            context.persisted = True
            logger.info(
                "s13_persistence_complete",
                submission_id=str(submission.id),
                result_id=str(result.id),
                source_status=context.source_status.value if context.source_status else None,
                headline_verdict=context.content_status.value if context.content_status else None,
                headline_check_status=context.headline_check_status.value if context.headline_check_status else None,
                date_status=context.date_status.value if context.date_status else None,
            )
            return context
        except Exception as exc:
            raise PersistenceError(stage_id=self.stage_id.value, message=f"Persistence failed: {exc}") from exc

    async def _write_cache_pointer(self, context: PipelineContext, submission_id: uuid.UUID, result) -> None:
        if not context.content_hash or not context.source_status:
            return
        ok, reason = result_is_reusable(result)
        if not ok:
            logger.info("s13_cache_pointer_skipped", reason=reason)
            return
        try:
            await CacheLookupStage.write_pointer(
                self.cache_service, context.content_hash, submission_id, context.source_status
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("s13_redis_cache_update_failed", error=str(exc))

    async def _notify(self, submission: Submission, context: PipelineContext) -> None:
        if not submission.submitter_id or not context.source_status:
            return
        await notify_preliminary_result(
            self.session,
            user_id=submission.submitter_id,
            submission_id=submission.id,
            headline=context.raw_headline or submission.headline,
        )

    async def _upsert_submission(self, context: PipelineContext) -> tuple[Submission, bool]:
        """(submission, already_done). Persists onto the submission this run
        was started for; a submission that merely shares an identity hash is
        never adopted (submissions carry owner/type/image provenance)."""
        existing = None
        if context.submission_id:
            existing = await self.submission_repo.get_by_id_or_none(context.submission_id)

        if existing:
            if existing.status in (SubmissionStatus.EXPERT_REVIEW, SubmissionStatus.FINALIZED, SubmissionStatus.ESCALATED):
                prior = await self.result_repo.get_by_submission_id(existing.id)
                if prior is not None and prior.source_status is not None:
                    return existing, True
            updated = await self.submission_repo.update(
                existing, status=SubmissionStatus.PROCESSING, content_hash=context.content_hash
            )
            return updated, False

        submission = Submission(
            submission_type=SubmissionType.SOURCE_BASED,
            headline=context.raw_headline[:2000],
            body_text=(context.raw_news_body or None),
            claimed_source_text=(context.raw_claimed_source or "")[:255] or None,
            published_date=context.published_date,
            submitter_id=context.submitter_id,
            content_hash=context.content_hash,
            status=SubmissionStatus.PROCESSING,
        )
        created = await self.submission_repo.create(submission)
        if context.submitter_id:
            await self._increment_submitter_total_submissions(context.submitter_id)
        return created, False

    async def _increment_submitter_total_submissions(self, submitter_id: uuid.UUID) -> None:
        """users.total_submissions cached counter - best effort only."""
        try:
            from app.features.auth.repository import UserRepository

            await UserRepository(self.session).increment_submission_count(submitter_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("s13_total_submissions_increment_failed", error=str(exc))

    async def _persist_articles(self, context: PipelineContext, submission_id: uuid.UUID) -> uuid.UUID | None:
        """Ranked articles; returns the DB id of the SELECTED source article
        (S08's choice). It is stored as `top_article_id`, which the result
        page and the expert view show first."""
        if not context.ranked_articles:
            return None
        selected_url = context.top_article.url if context.top_article else None
        selected_id: uuid.UUID | None = None
        new_models: list[RetrievedArticle] = []

        for article in context.ranked_articles:
            url_hash = compute_url_hash(article.url)
            existing = await self.article_repo.get_by_url_hash(submission_id, url_hash)
            if existing:
                if not existing.extraction_success and article.has_body:
                    existing.title = article.title[:500] if article.title else existing.title
                    existing.body = article.body
                    existing.author = article.author[:255] if article.author else existing.author
                    existing.published_date = article.published_date or existing.published_date
                    existing.rank_score = article.rank_score
                    existing.extraction_success = True
                    await self.session.flush()
                if article.url == selected_url:
                    selected_id = existing.id
                continue
            new_models.append(RetrievedArticle(
                submission_id=submission_id,
                url=article.url[:512],
                url_hash=url_hash,
                title=article.title[:500] if article.title else None,
                body=article.body,
                author=article.author[:255] if article.author else None,
                published_date=article.published_date,
                rank_score=article.rank_score,
                extraction_success=article.has_body,
            ))
        if new_models:
            for persisted in await self.article_repo.bulk_create(new_models):
                if persisted.url == selected_url:
                    selected_id = persisted.id
        return selected_id

    async def _persist_search_queries(self, context: PipelineContext, submission_id: uuid.UUID) -> None:
        if not context.search_queries:
            return
        per_type: Counter[str] = Counter(c.query_type for c in context.candidate_urls)
        self.session.add_all([
            SourceEvidenceQuery(
                submission_id=submission_id,
                query_text=qtext[:1000],
                query_type=qtype,
                search_provider=context.search_provider_used or SearchProvider.PY_GOOGLE_NEWS,
                results_count=per_type.get(qtype, 0),
            )
            for qtext, qtype in context.search_queries
        ])
        await self.session.flush()
