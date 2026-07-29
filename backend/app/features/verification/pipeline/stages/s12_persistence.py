from __future__ import annotations

import json
import uuid
from collections import Counter
from datetime import datetime

import structlog

from app.core.constants import ClaimStatus, PipelineStageID, SearchProvider
from app.core.exceptions import PersistenceError
from app.features.articles.models import RetrievedArticle, SearchQuery
from app.features.notifications.models import Notification
from app.features.verification.models import (
    VerificationLog,
    VerifiedClaim,
    VerificationResult,
)
from app.features.verification.pipeline.context import PipelineContext
from app.features.articles.repository import ArticleRepository
from app.features.verification.repository import ClaimRepository
from app.features.verification.repository import ResultRepository
from app.features.cache.cache_service import CacheService
from app.shared.utils.hashing import compute_url_hash
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


class PersistenceStage:

    stage_id = PipelineStageID.S12_PERSISTENCE

    def __init__(
        self,
        claim_repo: ClaimRepository,
        result_repo: ResultRepository,
        article_repo: ArticleRepository,
        cache_service: CacheService,
        session: AsyncSession | None = None,
    ) -> None:
        self.claim_repo = claim_repo
        self.result_repo = result_repo
        self.article_repo = article_repo
        self.cache_service = cache_service
        self.session = session or claim_repo.session

    async def execute(self, context: PipelineContext) -> PipelineContext:
        try:

            claim = await self._upsert_claim(context)
            context.claim_id = claim.id

            scores = context.scores
            top_article_id: uuid.UUID | None = None

            top_article_db_id = await self._persist_articles(context, claim.id)

            result = await self.result_repo.upsert_result(
                claim_id=claim.id,
                label=context.label,
                confidence=context.confidence,
                reasoning=context.reasoning,
                semantic_similarity=scores.semantic_similarity,
                entity_match=scores.entity_match,
                contradiction_score=scores.contradiction_score,
                keyword_overlap=scores.keyword_overlap,
                numerical_consistency=scores.numerical_consistency,
                top_article_id=top_article_db_id,
            )
            context.result_id = result.id

            await self._persist_search_queries(context, claim.id)

            await self._persist_logs(context, claim.id)

            await self.claim_repo.mark_completed(claim.id)

            import asyncio

            asyncio.create_task(self._update_redis_cache(context))

            await self._send_notification(claim, context)

            context.persisted = True
            logger.info(
                "s12_persistence_complete",
                claim_id=str(claim.id),
                result_id=str(result.id),
                label=context.label.value if context.label else None,
            )
            return context

        except Exception as exc:
            raise PersistenceError(
                stage_id=self.stage_id.value,
                message=f"Persistence failed: {exc}",
            ) from exc

    async def _send_notification(
        self, claim: VerifiedClaim, context: PipelineContext
    ) -> None:
        try:
            if not claim.submitter_id or not context.label:
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
                user_id=claim.submitter_id,
                title=f"Verification Complete: {label_display} ({confidence_pct})",
                body=f'Your claim "{headline_preview}" has been verified.',
                notification_type="VERIFICATION_COMPLETE",
                link_url=f"/verify/{claim.id}",
                is_read=False,
            )
            self.session.add(notif)
            await self.session.flush()
            logger.info(
                "s12_notification_sent",
                claim_id=str(claim.id),
                user_id=str(claim.submitter_id),
            )
        except Exception as exc:
            logger.warning("s12_notification_failed", error=str(exc))

    async def _upsert_claim(self, context: PipelineContext) -> VerifiedClaim:
        existing = None
        if context.claim_id:
            existing = await self.claim_repo.get_by_id_or_none(context.claim_id)
        if not existing and context.claim_hash:
            existing = await self.claim_repo.get_by_claim_hash(context.claim_hash)

        if existing:
            return await self.claim_repo.update(
                existing,
                status=ClaimStatus.PROCESSING,
                claim_hash=context.claim_hash,
                normalized_source=context.normalized_source,
            )

        claim = VerifiedClaim(
            headline=context.raw_headline[:2000],
            news_body=(context.raw_news_body or None),
            claimed_source=context.raw_claimed_source[:255],
            normalized_source=context.normalized_source,
            claim_hash=context.claim_hash,
            published_date=context.published_date,
            submitter_id=context.submitter_id,
            status=ClaimStatus.PROCESSING,
        )
        return await self.claim_repo.create(claim)

    async def _persist_articles(
        self, context: PipelineContext, claim_id: uuid.UUID
    ) -> uuid.UUID | None:
        if not context.ranked_articles:
            return None

        article_models: list[RetrievedArticle] = []
        top_article_url = context.top_article.url if context.top_article else None
        top_article_db_id: uuid.UUID | None = None

        for article in context.ranked_articles:
            url_hash = compute_url_hash(article.url)

            existing = await self.article_repo.get_by_url_hash(claim_id, url_hash)
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
                    await self.claim_repo.session.flush()
                    logger.debug(
                        "s12_updated_failed_article",
                        url_hash=url_hash,
                        url=article.url[:80],
                    )

                if article.url == top_article_url:
                    top_article_db_id = existing.id
                continue

            model = RetrievedArticle(
                claim_id=claim_id,
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
        self, context: PipelineContext, claim_id: uuid.UUID
    ) -> None:
        if not context.search_queries:
            return

        results_per_query_type: Counter[str] = Counter()
        for candidate in context.candidate_urls:
            results_per_query_type[candidate.query_type] += 1

        queries = [
            SearchQuery(
                claim_id=claim_id,
                query_text=qtext[:1000],
                query_type=qtype,
                search_provider=context.search_provider_used or SearchProvider.SEARXNG,
                results_count=results_per_query_type.get(qtype, 0),
            )
            for qtext, qtype in context.search_queries
        ]

        self.claim_repo.session.add_all(queries)
        await self.claim_repo.session.flush()

    async def _persist_logs(
        self, context: PipelineContext, claim_id: uuid.UUID
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
                    claim_id=claim_id,
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
        if not context.claim_hash or not context.label:
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
                "claim_id": str(context.claim_id) if context.claim_id else None,
                "normalized_source": context.normalized_source,
            }
            await self.cache_service.set_claim_result(
                context.claim_hash,
                json.dumps(payload, ensure_ascii=False),
            )
        except Exception as exc:
            logger.warning("s12_redis_cache_update_failed", error=str(exc))
