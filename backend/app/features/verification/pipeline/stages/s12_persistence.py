from __future__ import annotations

import uuid
from collections import Counter

import structlog

from app.core.constants import (
    VERIFICATION_PIPELINE_VERSION,
    PipelineStageID,
    SearchProvider,
    SubmissionStatus,
)
from app.core.exceptions import PersistenceError
from app.features.submissions.models import RetrievedArticle, SourceEvidenceQuery, Submission
from app.features.notifications.service import notify_once
from app.features.verification.pipeline.context import PipelineContext
from app.features.submissions.repository import RetrievedArticleRepository, SubmissionRepository
from app.features.verification.pipeline.stages.s02_cache_lookup import CacheLookupStage
from app.features.verification.repository import ResultRepository
from app.features.verification.reuse import result_is_reusable
from app.features.cache.cache_service import CacheService
from app.shared.utils.hashing import compute_url_hash
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


def _format_notification_verdict(context: PipelineContext) -> str:
    # INCOMPLETE is a failed check, never a confident result in either
    # direction — it must be reported as neither "not found" nor "confirmed".
    if context.source_status and context.source_status.value == "INCOMPLETE":
        return "⚠️ Source Check Incomplete"
    if context.source_status and context.source_status.value == "NOT_FOUND":
        return "🔍 Not Found in Source"

    content_display = {
        "MATCHED": "✅ Content Matched",
        "ALTERED": "⚠️ Content Altered",
        "INCOMPLETE": "⚠️ Content Check Incomplete",
    }.get(
        context.content_status.value if context.content_status else "",
        "✅ Source Confirmed",
    )

    if context.date_status and context.date_status.value == "MISMATCHED":
        return f"{content_display} · 📅 Date Mismatch"
    if context.date_status and context.date_status.value == "INCOMPLETE":
        return f"{content_display} · ⚠️ Date Check Incomplete"
    return content_display


class PersistenceStage:

    stage_id = PipelineStageID.S12_PERSISTENCE

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
                # Idempotent re-run (retry after a crash or a duplicate
                # dispatch): the automated result for this submission is
                # already saved, so nothing is rewritten and nothing is
                # notified twice.
                existing = await self.result_repo.get_by_submission_id(submission.id)
                context.result_id = existing.id if existing else None
                context.persisted = True
                logger.info("s12_already_persisted_skipping", submission_id=str(submission.id))
                return context

            scores = context.scores
            top_article_db_id = await self._persist_articles(context, submission.id)

            result = await self.result_repo.upsert_result(
                submission_id=submission.id,
                source_status=context.source_status,
                content_status=context.content_status,
                date_status=context.date_status,
                confidence=context.confidence,
                reasoning=context.reasoning,
                semantic_similarity=scores.semantic_similarity,
                entity_match=scores.entity_match,
                contradiction_score=scores.contradiction_score,
                keyword_overlap=scores.keyword_overlap,
                numerical_consistency=scores.numerical_consistency,
                top_article_id=top_article_db_id,
                avg_verification_time_ms=context.elapsed_ms,
                manipulation_flags=context.manipulation_flags.model_dump(mode="json"),
                headline_similarity=scores.headline_similarity,
                body_similarity=scores.body_similarity,
                passage_similarity=scores.passage_similarity,
                headline_keyword_coverage=scores.headline_keyword_coverage,
                passage_keyword_coverage=scores.passage_keyword_coverage,
                body_keyword_coverage=scores.body_keyword_coverage,
                claim_scope=context.claim_scope.value,
                pipeline_version=VERIFICATION_PIPELINE_VERSION,
                analysis_details=context.analysis.model_dump(mode="json"),
            )
            context.result_id = result.id

            await self._persist_search_queries(context, submission.id)
            for stage, duration_ms in context.stage_timings.items():
                event_logger = logger.error if stage in context.stage_errors else logger.info
                event_logger(
                    "verification_stage_completed",
                    submission_id=str(submission.id),
                    stage=stage,
                    duration_ms=duration_ms,
                    error=context.stage_errors.get(stage),
                )

            # Every automated result enters expert review - including a
            # reviewable INCOMPLETE one. No automated overall verdict (and no
            # legacy TRUE/FALSE consensus label) is derived or stored.
            await self.submission_repo.mark_ai_done(submission.id)
            await self.submission_repo.set_phase(submission.id, "DONE")

            await self._write_cache_pointer(context, submission.id, result)
            await self._send_submitter_notification(submission, context)
            await self._notify_experts_of_new_review(submission, context)

            context.persisted = True
            logger.info(
                "s12_persistence_complete",
                submission_id=str(submission.id),
                result_id=str(result.id),
                source_status=context.source_status.value if context.source_status else None,
                content_status=context.content_status.value if context.content_status else None,
                date_status=context.date_status.value if context.date_status else None,
            )
            return context

        except Exception as exc:
            raise PersistenceError(
                stage_id=self.stage_id.value,
                message=f"Persistence failed: {exc}",
            ) from exc

    async def _write_cache_pointer(self, context, submission_id, result) -> None:
        """Record this submission as the latest complete result for the claim
        identity - only when it is a reusable (complete, current) result."""
        if not context.content_hash or not context.source_status:
            return
        ok, reason = result_is_reusable(result)
        if not ok:
            logger.info("s12_cache_pointer_skipped", reason=reason)
            return
        try:
            await CacheLookupStage.write_pointer(
                self.cache_service, context.content_hash, submission_id, context.source_status
            )
        except Exception as exc:
            logger.warning("s12_redis_cache_update_failed", error=str(exc))

    async def _send_submitter_notification(
        self, submission: Submission, context: PipelineContext
    ) -> None:
        if not submission.submitter_id or not context.source_status:
            return
        label_display = _format_notification_verdict(context)
        headline_preview = (context.raw_headline or submission.headline or "")[:80]
        if len(context.raw_headline or "") > 80:
            headline_preview += "…"
        # No confidence percentage and no overall verdict: the result is a
        # preliminary automated check awaiting expert review.
        await notify_once(
            self.session,
            user_id=submission.submitter_id,
            notification_type="VERIFICATION_COMPLETE",
            link_url=f"/verify/{submission.id}",
            title=f"Automated check complete: {label_display}",
            body=(
                f'Your claim "{headline_preview}" has a preliminary automated result '
                "and is now with our experts for review."
            ),
        )

    async def _notify_experts_of_new_review(
        self, submission: Submission, context: PipelineContext
    ) -> None:
        """Broadcast to every active expert that a new claim is available in
        the review queue. Best-effort, never allowed to fail the pipeline."""
        try:
            from sqlalchemy import select

            from app.features.auth.models import User

            stmt = select(User.id).where(User.role == "expert", User.is_active.is_(True))
            expert_ids = (await self.session.execute(stmt)).scalars().all()
            headline_preview = (context.raw_headline or submission.headline or "")[:80]
            if len(context.raw_headline or "") > 80:
                headline_preview += "…"
            for expert_id in expert_ids:
                await notify_once(
                    self.session,
                    user_id=expert_id,
                    notification_type="EXPERT_REVIEW_AVAILABLE",
                    link_url=f"/expert/queue/{submission.id}",
                    title="New claim available for review",
                    body=f'A new submission "{headline_preview}" is ready for expert review.',
                )
        except Exception as exc:
            logger.warning("s12_expert_notifications_failed", error=str(exc))

    async def _upsert_submission(
        self, context: PipelineContext
    ) -> tuple[Submission, bool]:
        """(submission, already_done).

        Persists onto the submission this run was started for. A claim that
        merely shares an identity hash with another submission is NEVER
        adopted: submissions carry owner/type/image/OCR provenance and are
        not interchangeable (the previous hash lookup could overwrite an
        expert-reviewed submission on a forced refresh).
        """
        existing = None
        if context.submission_id:
            existing = await self.submission_repo.get_by_id_or_none(context.submission_id)

        if existing:
            done_states = (
                SubmissionStatus.EXPERT_REVIEW,
                SubmissionStatus.FINALIZED,
                SubmissionStatus.ESCALATED,
            )
            if existing.status in done_states:
                prior = await self.result_repo.get_by_submission_id(existing.id)
                if prior is not None and prior.source_status is not None:
                    return existing, True
            updated = await self.submission_repo.update(
                existing,
                status=SubmissionStatus.PROCESSING,
                content_hash=context.content_hash,
            )
            return updated, False

        from app.core.constants import SubmissionType

        submission = Submission(
            submission_type=SubmissionType.SOURCE_BASED,
            headline=context.raw_headline[:2000],
            body_text=(context.raw_news_body or None),
            claimed_source_text=context.raw_claimed_source[:255],
            published_date=context.published_date,
            submitter_id=context.submitter_id,
            content_hash=context.content_hash,
            status=SubmissionStatus.PROCESSING,
        )
        created = await self.submission_repo.create(submission)
        if context.submitter_id:
            await self._increment_submitter_total_submissions(context.submitter_id)
        return created, False

    async def _increment_submitter_total_submissions(
        self, submitter_id: uuid.UUID
    ) -> None:
        """DatabaseDescription.pdf Table 4.1 — users.total_submissions cached
        counter. Best-effort DB-store side effect only; never allowed to fail
        the pipeline."""
        try:
            from app.features.auth.models import User

            stmt = (
                update(User)
                .where(User.id == submitter_id)
                .values(total_submissions=User.total_submissions + 1)
            )
            await self.session.execute(stmt)
            await self.session.flush()
        except Exception as exc:
            logger.warning("s12_total_submissions_increment_failed", error=str(exc))

    async def _persist_articles(
        self, context: PipelineContext, submission_id: uuid.UUID
    ) -> uuid.UUID | None:
        if not context.ranked_articles:
            return None

        article_models: list[RetrievedArticle] = []
        top_article_url = context.top_article.url if context.top_article else None
        top_article_db_id: uuid.UUID | None = None

        for article in context.ranked_articles:
            url_hash = compute_url_hash(article.url)

            existing = await self.article_repo.get_by_url_hash(submission_id, url_hash)
            if existing:

                if not existing.extraction_success and article.has_body:
                    existing.title = (
                        article.title[:500] if article.title else existing.title
                    )
                    existing.body = article.body
                    existing.author = (
                        article.author[:255] if article.author else existing.author
                    )
                    existing.published_date = (
                        article.published_date or existing.published_date
                    )
                    existing.rank_score = article.rank_score
                    existing.extraction_success = True
                    await self.submission_repo.session.flush()
                    logger.debug(
                        "s12_updated_failed_article",
                        url_hash=url_hash,
                        url=article.url[:80],
                    )

                if article.url == top_article_url:
                    top_article_db_id = existing.id
                continue

            model = RetrievedArticle(
                submission_id=submission_id,
                url=article.url[:512],
                url_hash=url_hash,
                title=article.title[:500] if article.title else None,
                body=article.body,
                author=article.author[:255] if article.author else None,
                published_date=article.published_date,
                rank_score=article.rank_score,
                extraction_success=article.has_body,
            )
            article_models.append(model)

        if article_models:
            persisted = await self.article_repo.bulk_create(article_models)

            for persisted_article in persisted:
                if persisted_article.url == top_article_url:
                    top_article_db_id = persisted_article.id
                    break

        return top_article_db_id

    async def _persist_search_queries(
        self, context: PipelineContext, submission_id: uuid.UUID
    ) -> None:
        if not context.search_queries:
            return

        results_per_query_type: Counter[str] = Counter()
        for candidate in context.candidate_urls:
            results_per_query_type[candidate.query_type] += 1

        queries = [
            SourceEvidenceQuery(
                submission_id=submission_id,
                query_text=qtext[:1000],
                query_type=qtype,
                search_provider=context.search_provider_used or SearchProvider.SEARXNG,
                results_count=results_per_query_type.get(qtype, 0),
            )
            for qtext, qtype in context.search_queries
        ]

        self.submission_repo.session.add_all(queries)
        await self.submission_repo.session.flush()
