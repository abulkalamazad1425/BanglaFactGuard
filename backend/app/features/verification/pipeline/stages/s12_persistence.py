from __future__ import annotations

import json
import uuid
from collections import Counter
from datetime import datetime

import structlog

from app.core.constants import PipelineStageID, SearchProvider, SubmissionStatus
from app.core.exceptions import PersistenceError
from app.features.submissions.models import RetrievedArticleV2, SourceEvidenceQuery, Submission
from app.features.notifications.models import Notification
from app.features.verification.models import VerificationLog
from app.features.verification.pipeline.context import PipelineContext
from app.features.submissions.repository import RetrievedArticleV2Repository, SubmissionRepository
from app.features.verification.repository import ResultV2Repository
from app.features.cache.cache_service import CacheService
from app.shared.utils.hashing import compute_url_hash
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


class PersistenceStage:

    stage_id = PipelineStageID.S12_PERSISTENCE

    def __init__(
        self,
        submission_repo: SubmissionRepository,
        result_repo: ResultV2Repository,
        article_repo: RetrievedArticleV2Repository,
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

            submission = await self._upsert_submission(context)
            context.submission_id = submission.id

            scores = context.scores

            top_article_db_id = await self._persist_articles(context, submission.id)

            result = await self.result_repo.upsert_result(
                submission_id=submission.id,
                label=context.label,
                confidence=context.confidence,
                reasoning=context.reasoning,
                semantic_similarity=scores.semantic_similarity,
                entity_match=scores.entity_match,
                contradiction_score=scores.contradiction_score,
                keyword_overlap=scores.keyword_overlap,
                numerical_consistency=scores.numerical_consistency,
                top_article_id=top_article_db_id,
                avg_verification_time_ms=context.elapsed_ms,
            )
            context.result_id = result.id

            await self._persist_search_queries(context, submission.id)

            await self._persist_logs(context, submission.id)

            # Every AI-verified submission enters expert review (PDF §2.1: "Every
            # verification request must first receive a clearly marked AI-assisted
            # preliminary result... The claim is then sent to human experts for
            # review").
            await self.submission_repo.mark_ai_done(submission.id)

            import asyncio

            asyncio.create_task(self._update_redis_cache(context))

            await self._send_submitter_notification(submission, context)
            await self._notify_experts_of_new_review(submission, context)

            context.persisted = True
            logger.info(
                "s12_persistence_complete",
                submission_id=str(submission.id),
                result_id=str(result.id),
                label=context.label.value if context.label else None,
            )
            return context

        except Exception as exc:
            raise PersistenceError(
                stage_id=self.stage_id.value,
                message=f"Persistence failed: {exc}",
            ) from exc

    async def _send_submitter_notification(
        self, submission: Submission, context: PipelineContext
    ) -> None:
        try:
            if not submission.submitter_id or not context.label:
                return
            label_display = {
                "TRUE": "✅ True",
                "FALSE": "❌ False",
                "PARTIALLY_TRUE": "⚠️ Partially True",
                "NOT_FOUND_IN_CLAIMED_SOURCE": "🔍 Not Found in Source",
            }.get(context.label.value, context.label.value)
            confidence_pct = f"{(context.confidence or 0) * 100:.0f}%"
            headline_preview = (context.raw_headline or "")[:80]
            if len(context.raw_headline or "") > 80:
                headline_preview += "…"
            notif = Notification(
                user_id=submission.submitter_id,
                title=f"Verification Complete: {label_display} ({confidence_pct})",
                body=f'Your claim "{headline_preview}" has been AI-verified and is now with our experts for review.',
                notification_type="VERIFICATION_COMPLETE",
                link_url=f"/verify/{submission.id}",
                is_read=False,
            )
            self.session.add(notif)
            await self.session.flush()
            logger.info(
                "s12_submitter_notification_sent",
                submission_id=str(submission.id),
                user_id=str(submission.submitter_id),
            )
        except Exception as exc:
            logger.warning("s12_submitter_notification_failed", error=str(exc))

    async def _notify_experts_of_new_review(
        self, submission: Submission, context: PipelineContext
    ) -> None:
        """Broadcast to every active expert that a new claim is available in the
        review queue (PDF §2.2: "experts should receive notifications when a new
        review is assigned to them"). The system uses a shared pull queue rather
        than per-expert assignment, so "assigned" is interpreted as "available to
        pick up." Best-effort, never allowed to fail the pipeline."""
        try:
            from app.features.auth.models import User

            stmt = select(User.id).where(User.role == "expert", User.is_active.is_(True))
            expert_ids = (await self.session.execute(stmt)).scalars().all()
            if not expert_ids:
                return

            headline_preview = (context.raw_headline or "")[:80]
            if len(context.raw_headline or "") > 80:
                headline_preview += "…"

            notifs = [
                Notification(
                    user_id=expert_id,
                    title="New claim available for review",
                    body=f'A new submission "{headline_preview}" is ready for expert review.',
                    notification_type="EXPERT_REVIEW_AVAILABLE",
                    link_url=f"/expert/queue/{submission.id}",
                    is_read=False,
                )
                for expert_id in expert_ids
            ]
            self.session.add_all(notifs)
            await self.session.flush()
            logger.info(
                "s12_expert_notifications_sent",
                submission_id=str(submission.id),
                expert_count=len(expert_ids),
            )
        except Exception as exc:
            logger.warning("s12_expert_notifications_failed", error=str(exc))

    async def _upsert_submission(self, context: PipelineContext) -> Submission:
        existing = None
        if context.submission_id:
            existing = await self.submission_repo.get_by_id_or_none(context.submission_id)
        if not existing and context.content_hash:
            existing = await self.submission_repo.get_by_content_hash(context.content_hash)

        if existing:
            return await self.submission_repo.update(
                existing,
                status=SubmissionStatus.PROCESSING,
                content_hash=context.content_hash,
            )

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
        return created

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

        article_models: list[RetrievedArticleV2] = []
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

            model = RetrievedArticleV2(
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

    async def _persist_logs(
        self, context: PipelineContext, submission_id: uuid.UUID
    ) -> None:
        from app.core.constants import LogLevel, PipelineStageID as SID

        log_entries: list[VerificationLog] = []

        for stage_key, duration_ms in context.stage_timings.items():
            try:
                stage_id = SID(stage_key)
            except ValueError:
                continue

            level = (
                LogLevel.ERROR if stage_key in context.stage_errors else LogLevel.INFO
            )
            message = context.stage_errors.get(
                stage_key, f"Stage {stage_key} completed"
            )

            log_entries.append(
                VerificationLog(
                    submission_id=submission_id,
                    stage=stage_id,
                    level=level,
                    message=message,
                    metadata_={"duration_ms": duration_ms},
                    duration_ms=duration_ms,
                )
            )

        if log_entries:
            await self.result_repo.bulk_log(log_entries)

    async def _update_redis_cache(self, context: PipelineContext) -> None:
        if not context.content_hash or not context.label:
            return
        try:
            payload = {
                "label": context.label.value,
                "confidence": context.confidence,
                "reasoning": context.reasoning,
                "scores": context.scores.model_dump(),
                "manipulation_flags": context.manipulation_flags.model_dump(),
                "matched_articles": [
                    a.model_dump(mode="json") for a in context.ranked_articles[:3]
                ],
                "submission_id": str(context.submission_id) if context.submission_id else None,
                "normalized_source": context.normalized_source,
            }
            await self.cache_service.set_claim_result(
                context.content_hash,
                json.dumps(payload, ensure_ascii=False),
            )
        except Exception as exc:
            logger.warning("s12_redis_cache_update_failed", error=str(exc))
