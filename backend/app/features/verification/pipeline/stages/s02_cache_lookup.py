from __future__ import annotations

import json

import structlog

from app.core.constants import ContentStatus, DateStatus, PipelineStageID, SourceStatus
from app.features.verification.pipeline.context import PipelineContext
from app.features.submissions.repository import SubmissionRepository
from app.features.verification.repository import ResultV2Repository
from app.features.articles.schemas import RankedArticleSchema
from app.features.verification.schemas import (
    ManipulationFlagsSchema,
    VerificationScoresSchema,
)
from app.features.cache.cache_service import CacheService

logger = structlog.get_logger(__name__)


class CacheLookupStage:

    stage_id = PipelineStageID.S02_CACHE_LOOKUP

    def __init__(
        self,
        cache_service: CacheService,
        submission_repo: SubmissionRepository,
        result_repo: ResultV2Repository,
    ) -> None:

        self.cache_service = cache_service
        self.submission_repo = submission_repo
        self.result_repo = result_repo

    async def execute(self, context: PipelineContext) -> PipelineContext:

        log = logger.bind(
            stage=self.stage_id.value,
            content_hash=context.content_hash,
        )

        if context.force_refresh:
            log.info("cache_bypassed_force_refresh")
            context.cache_hit = False
            return context

        if not context.content_hash:
            log.warning("content_hash_missing_skipping_cache")
            context.cache_hit = False
            return context

        try:
            redis_hit = await self._check_redis(context, log)
            if redis_hit:
                return context
        except Exception as exc:
            log.warning("redis_cache_error", error=str(exc))

        try:
            db_hit = await self._check_db(context, log)
            if db_hit:
                return context
        except Exception as exc:
            log.warning("db_cache_error", error=str(exc))

        log.info("cache_miss")
        context.cache_hit = False
        return context

    async def _check_redis(
        self,
        context: PipelineContext,
        log: structlog.BoundLogger,
    ) -> bool:

        cached_bytes = await self.cache_service.get_claim_result(context.content_hash)

        if cached_bytes is None:
            log.debug("redis_miss")
            return False

        try:
            cached_data: dict = json.loads(cached_bytes)
            self._populate_context_from_cache(context, cached_data)
            log.info(
                "redis_hit",
                source_status=context.cached_source_status,
                content_status=context.cached_content_status,
                date_status=context.cached_date_status,
            )
            return True
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            log.warning("redis_cache_deserialisation_error", error=str(exc))

            return False

    async def _check_db(
        self,
        context: PipelineContext,
        log: structlog.BoundLogger,
    ) -> bool:

        submission = await self.submission_repo.get_verified_by_content_hash(
            context.content_hash
        )
        if submission is None:
            log.debug("db_miss")
            return False

        result = await self.result_repo.get_by_submission_id(submission.id)
        if result is None or result.source_status is None:
            log.debug("db_submission_found_but_no_result", submission_id=str(submission.id))
            return False

        context.submission_id = submission.id
        context.normalized_source = context.normalized_source
        context.cached_source_status = SourceStatus(result.source_status)
        context.cached_content_status = (
            ContentStatus(result.content_status) if result.content_status else None
        )
        context.cached_date_status = (
            DateStatus(result.date_status) if result.date_status else None
        )
        context.cached_confidence = result.confidence
        context.cached_reasoning = result.reasoning or ""
        context.cached_scores = VerificationScoresSchema(
            semantic_similarity=result.semantic_similarity,
            entity_match=result.entity_match,
            contradiction_score=result.contradiction_score,
            keyword_overlap=result.keyword_overlap,
            numerical_consistency=result.numerical_consistency,
        )
        context.cached_manipulation_flags = ManipulationFlagsSchema()
        context.cache_hit = True

        log.info(
            "db_hit",
            submission_id=str(submission.id),
            source_status=context.cached_source_status.value,
            content_status=(
                context.cached_content_status.value
                if context.cached_content_status
                else None
            ),
            date_status=(
                context.cached_date_status.value if context.cached_date_status else None
            ),
        )

        try:
            await self._write_to_redis(context)
        except Exception as exc:
            log.warning("redis_write_back_failed", error=str(exc))

        return True

    def _populate_context_from_cache(
        self, context: PipelineContext, data: dict
    ) -> None:

        context.cache_hit = True
        context.cached_source_status = SourceStatus(data["source_status"])
        context.cached_content_status = (
            ContentStatus(data["content_status"]) if data.get("content_status") else None
        )
        context.cached_date_status = (
            DateStatus(data["date_status"]) if data.get("date_status") else None
        )
        context.cached_confidence = float(data["confidence"])
        context.cached_reasoning = data.get("reasoning", "")
        context.cached_scores = VerificationScoresSchema(**data.get("scores", {}))
        context.cached_manipulation_flags = ManipulationFlagsSchema(
            **data.get("manipulation_flags", {})
        )

        raw_articles = data.get("matched_articles", [])
        context.cached_matched_articles = [
            RankedArticleSchema(**a) for a in raw_articles
        ]
        if data.get("submission_id"):
            import uuid as _uuid

            context.submission_id = _uuid.UUID(data["submission_id"])
        if data.get("normalized_source"):
            context.normalized_source = data["normalized_source"]

    async def _write_to_redis(self, context: PipelineContext) -> None:

        payload = {
            "source_status": (
                context.cached_source_status.value
                if context.cached_source_status
                else None
            ),
            "content_status": (
                context.cached_content_status.value
                if context.cached_content_status
                else None
            ),
            "date_status": (
                context.cached_date_status.value if context.cached_date_status else None
            ),
            "confidence": context.cached_confidence,
            "reasoning": context.cached_reasoning,
            "scores": (
                context.cached_scores.model_dump() if context.cached_scores else {}
            ),
            "manipulation_flags": (
                context.cached_manipulation_flags.model_dump()
                if context.cached_manipulation_flags
                else {}
            ),
            "matched_articles": [
                a.model_dump(mode="json") for a in context.cached_matched_articles
            ],
            "submission_id": str(context.submission_id) if context.submission_id else None,
            "normalized_source": context.normalized_source,
        }
        await self.cache_service.set_claim_result(
            context.content_hash,
            json.dumps(payload, ensure_ascii=False),
        )
