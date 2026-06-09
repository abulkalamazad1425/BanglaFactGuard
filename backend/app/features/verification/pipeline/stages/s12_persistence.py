"""
app/pipelines/stages/s12_persistence.py
=========================================
Stage 12: Persistence (CRITICAL)

## Responsibility

Persist all pipeline outputs to PostgreSQL and update the Redis cache:

1. Upsert `verified_claims` record (update status to COMPLETED, store hash).
2. Upsert `verification_results` record with all scores and verdict.
3. Bulk-insert `retrieved_articles` (deduplicated by url_hash).
4. Bulk-insert `search_queries` for audit trail.
5. Bulk-insert `verification_logs` from `context.pending_log_entries`
   + per-stage timing entries.
6. Write final result to Redis (claim cache key) for future L1 hits.

## Criticality: CRITICAL
If persistence fails, the orchestrator marks the claim as FAILED.
A PipelineError is raised so the FastAPI exception handler can return 500.

## Transaction safety
All DB writes are executed within a single SQLAlchemy session managed by
the caller (VerificationService). The session commits only after this stage
succeeds — guaranteeing atomicity across all five writes.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime

import structlog

from app.core.constants import ClaimStatus, PipelineStageID, SearchProvider
from app.core.exceptions import PersistenceError
from app.features.articles.models import RetrievedArticle, SearchQuery
from app.features.verification.models import VerificationLog, VerifiedClaim, VerificationResult
from app.features.verification.pipeline.context import PipelineContext
from app.features.articles.repository import ArticleRepository
from app.features.verification.repository import ClaimRepository
from app.features.verification.repository import ResultRepository
from app.features.cache.cache_service import CacheService
from app.shared.utils.hashing import compute_url_hash

logger = structlog.get_logger(__name__)


class PersistenceStage:
    """
    Stage 12 (CRITICAL): Persist the full pipeline result to PostgreSQL and Redis.

    Dependencies:
        claim_repo:   For upserting VerifiedClaim.
        result_repo:  For upserting VerificationResult + bulk logging.
        article_repo: For bulk-inserting RetrievedArticle records.
        cache_service:For updating Redis claim cache.
    """

    stage_id = PipelineStageID.S12_PERSISTENCE

    def __init__(
        self,
        claim_repo: ClaimRepository,
        result_repo: ResultRepository,
        article_repo: ArticleRepository,
        cache_service: CacheService,
    ) -> None:
        self.claim_repo = claim_repo
        self.result_repo = result_repo
        self.article_repo = article_repo
        self.cache_service = cache_service

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """
        Persist all pipeline outputs atomically within the shared session.

        Args:
            context: Fully processed pipeline context with all stage outputs.

        Returns:
            Context with result_id and persisted=True set.

        Raises:
            PersistenceError: On any DB write failure (CRITICAL — triggers rollback).
        """
        try:
            # ------------------------------------------------------------------
            # 1. Upsert VerifiedClaim
            # ------------------------------------------------------------------
            claim = await self._upsert_claim(context)
            context.claim_id = claim.id

            # ------------------------------------------------------------------
            # 2. Upsert VerificationResult
            # ------------------------------------------------------------------
            scores = context.scores
            top_article_id: uuid.UUID | None = None

            # We need the article's DB ID — will be set after article insert below
            # So we insert articles first, then result
            # ------------------------------------------------------------------
            # 3. Bulk-insert RetrievedArticles
            # ------------------------------------------------------------------
            top_article_db_id = await self._persist_articles(context, claim.id)

            # Now insert the result with the top article ID
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

            # ------------------------------------------------------------------
            # 4. Bulk-insert SearchQueries
            # ------------------------------------------------------------------
            await self._persist_search_queries(context, claim.id)

            # ------------------------------------------------------------------
            # 5. Bulk-insert VerificationLogs (timings + pending entries)
            # ------------------------------------------------------------------
            await self._persist_logs(context, claim.id)

            # ------------------------------------------------------------------
            # 6. Update claim status to COMPLETED
            # ------------------------------------------------------------------
            await self.claim_repo.mark_completed(claim.id)

            # ------------------------------------------------------------------
            # 7. Write result to Redis (fire-and-forget)
            # ------------------------------------------------------------------
            import asyncio
            asyncio.create_task(self._update_redis_cache(context))

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

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _upsert_claim(self, context: PipelineContext) -> VerifiedClaim:
        """Fetch existing claim by ID or create a new one."""
        if context.claim_id:
            existing = await self.claim_repo.get_by_id_or_none(context.claim_id)
            if existing:
                return await self.claim_repo.update(
                    existing,
                    status=ClaimStatus.PROCESSING,
                    claim_hash=context.claim_hash,
                    normalized_source=context.normalized_source,
                )

        # Create new claim record
        claim = VerifiedClaim(
            headline=context.raw_headline[:2000],
            news_body=(context.raw_news_body or None),
            claimed_source=context.raw_claimed_source[:255],
            normalized_source=context.normalized_source,
            claim_hash=context.claim_hash,
            published_date=context.published_date,
            status=ClaimStatus.PROCESSING,
        )
        return await self.claim_repo.create(claim)

    async def _persist_articles(
        self, context: PipelineContext, claim_id: uuid.UUID
    ) -> uuid.UUID | None:
        """
        Bulk-insert all ranked articles. Returns DB UUID of top article.
        """
        if not context.ranked_articles:
            return None

        article_models: list[RetrievedArticle] = []
        top_article_url = context.top_article.url if context.top_article else None
        top_article_db_id: uuid.UUID | None = None

        for article in context.ranked_articles:
            url_hash = compute_url_hash(article.url)
            # Skip if already exists for this claim
            if await self.article_repo.url_already_retrieved(claim_id, url_hash):
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
            # Find DB ID of top article
            for persisted_article in persisted:
                if persisted_article.url == top_article_url:
                    top_article_db_id = persisted_article.id
                    break

        return top_article_db_id

    async def _persist_search_queries(
        self, context: PipelineContext, claim_id: uuid.UUID
    ) -> None:
        """Bulk-insert SearchQuery records for audit trail."""
        if not context.search_queries:
            return

        queries = [
            SearchQuery(
                claim_id=claim_id,
                query_text=qtext[:1000],
                query_type=qtype,
                search_provider=context.search_provider_used or SearchProvider.SEARXNG,
                results_count=0,  # Aggregate count not tracked per query
            )
            for qtext, qtype in context.search_queries
        ]
        from sqlalchemy.ext.asyncio import AsyncSession
        # Use the session via claim_repo
        self.claim_repo.session.add_all(queries)
        await self.claim_repo.session.flush()

    async def _persist_logs(
        self, context: PipelineContext, claim_id: uuid.UUID
    ) -> None:
        """Bulk-insert stage timing logs."""
        from app.core.constants import LogLevel, PipelineStageID as SID

        log_entries: list[VerificationLog] = []

        # Create timing log entries for all completed stages
        for stage_key, duration_ms in context.stage_timings.items():
            try:
                stage_id = SID(stage_key)
            except ValueError:
                continue

            level = LogLevel.ERROR if stage_key in context.stage_errors else LogLevel.INFO
            message = context.stage_errors.get(stage_key, f"Stage {stage_key} completed")

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
        """Write the final result to Redis for future L1 cache hits."""
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
        except Exception as exc:  # noqa: BLE001
            logger.warning("s12_redis_cache_update_failed", error=str(exc))

